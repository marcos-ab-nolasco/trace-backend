"""Service for processing client answers received via WhatsApp."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.processed_webhook import ProcessedWebhook
from src.db.models.template_version import TemplateVersion
from src.db.models.whatsapp_message import MessageDirection, MessageStatus, WhatsAppMessage
from src.db.models.whatsapp_session import SessionStatus, WhatsAppSession
from src.services.briefing.orchestrator import BriefingOrchestrator
from src.services.whatsapp.whatsapp_account_service import WhatsAppAccountService
from src.services.whatsapp.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class AnswerProcessorService:
    """Service for processing client answers in briefing conversations."""

    def __init__(self, db_session: AsyncSession):
        """Initialize answer processor with database session.

        Args:
            db_session: AsyncSession for database operations
        """
        self.db_session = db_session
        self.orchestrator = BriefingOrchestrator(db_session)

    async def process_client_answer(
        self,
        phone_number: str,
        answer_text: str,
        wa_message_id: str,
        session_id: UUID | None = None,
        phone_number_id: str | None = None,
    ) -> dict[str, Any]:
        """Process answer from client received via WhatsApp.

        Implements transaction management (Option C: Idempotency with Rollback):
        - All DB operations wrapped in explicit transaction
        - WhatsApp sends happen OUTSIDE transaction
        - On WhatsApp failure, exception propagates (triggers webhook retry)
        - Idempotency check prevents duplicate processing on retry

        Args:
            phone_number: Client's phone number
            answer_text: The answer text
            wa_message_id: WhatsApp message ID (used for idempotency)
            session_id: Optional WhatsApp session ID
            phone_number_id: Optional WhatsApp phone number ID from webhook

        Returns:
            Dict with processing result including success status, briefing info, and next question

        Raises:
            Exception: If WhatsApp send fails (to trigger webhook retry)
        """
        # ====================================================================
        # PRE-TRANSACTION CHECKS (non-mutating operations)
        # ====================================================================
        # Find client first (needed for both idempotency and normal processing)
        client = await self._find_client_by_phone(phone_number)
        if not client:
            logger.warning(f"Client not found for phone {phone_number}")
            return {
                "success": False,
                "error": "client_not_found",
                "message": "Cliente não encontrado no sistema.",
            }

        # ====================================================================
        # IDEMPOTENCY CHECK (after finding client, before transaction)
        # ====================================================================
        existing_webhook = await self._check_if_webhook_already_processed(wa_message_id)
        if existing_webhook:
            logger.info(
                f"Webhook {wa_message_id} already processed, attempting WhatsApp retry if needed"
            )
            cached_result = existing_webhook.result_data or {
                "success": True,
                "message": "Already processed (idempotent)",
            }

            # On retry after WhatsApp failure, try sending the message again
            # (DB operations already committed, just retry the WhatsApp send)
            try:
                if cached_result.get("completed"):
                    # Completion message needed
                    await self._send_completion_message(client, phone_number_id)
                elif cached_result.get("next_question"):
                    # Next question needed
                    await self._send_next_question(
                        client=client,
                        question_text=cached_result["next_question"],
                        phone_number_id=phone_number_id,
                    )
                logger.info(f"WhatsApp retry successful for webhook {wa_message_id}")
            except Exception as e:
                # WhatsApp still failing, propagate for another retry
                logger.error(f"WhatsApp retry failed for webhook {wa_message_id}: {e}")
                raise

            return cached_result

        # Continue with normal processing if not already processed
        # Client already found above, continue with active briefing check
        active_briefing = await self._find_active_briefing(client.id)
        if not active_briefing:
            logger.warning(f"No active briefing for client {client.id}")
            # Send a friendly message to client (no transaction needed)
            await self._send_no_active_briefing_message(client, phone_number_id)
            return {
                "success": False,
                "error": "no_active_briefing",
                "message": "Nenhum briefing ativo encontrado para este cliente.",
                "no_active_briefing": True,
            }

        # ====================================================================
        # TRANSACTION BLOCK (all DB mutations happen here)
        # ====================================================================
        # Variables to hold data needed after transaction commits
        next_question_text: str | None = None
        completion_message_needed = False
        result_data: dict[str, Any] = {}

        try:
            # All DB operations (no explicit begin, works with existing transaction)
            logger.debug(f"Starting DB operations for webhook {wa_message_id}")

            # 1. Find or create WhatsApp session
            wa_session = await self._get_or_create_session(
                client_id=client.id,
                phone_number=phone_number,
                session_id=session_id,
            )

            # 2. Save incoming message
            await self._save_incoming_message(
                session_id=wa_session.id,
                wa_message_id=wa_message_id,
                answer_text=answer_text,
            )

            # 3. Link session to briefing if needed
            if wa_session.briefing_id != active_briefing.id:
                wa_session.briefing_id = active_briefing.id
                await self.db_session.flush()

            # 4. Process answer via orchestrator (with auto_commit=False)
            current_question = active_briefing.current_question_order
            updated_briefing = await self.orchestrator.process_answer(
                briefing_id=active_briefing.id,
                question_order=current_question,
                answer=answer_text,
                auto_commit=False,  # We control the transaction
            )

            logger.info(
                f"Processed answer for briefing {active_briefing.id}, question {current_question}"
            )

            # 5. Get next question data
            next_question_data = await self.orchestrator.next_question(updated_briefing.id)

            # 6. Determine if briefing should be completed
            should_complete = await self._should_complete_briefing(updated_briefing)

            if should_complete:
                # Complete the briefing (with auto_commit=False)
                completed_briefing = await self.orchestrator.complete_briefing(
                    updated_briefing.id, auto_commit=False
                )
                logger.info(f"Completed briefing {completed_briefing.id}")

                completion_message_needed = True
                result_data = {
                    "success": True,
                    "briefing_id": completed_briefing.id,
                    "question_number": current_question,
                    "next_question": None,
                    "completed": True,
                    "status": BriefingStatus.COMPLETED.value,
                }
            elif next_question_data:
                next_question_text = next_question_data["question"]
                result_data = {
                    "success": True,
                    "briefing_id": updated_briefing.id,
                    "question_number": current_question,
                    "next_question": next_question_text,
                    "completed": False,
                    "status": updated_briefing.status.value,
                }
            else:
                # No more questions but not completed yet (edge case)
                result_data = {
                    "success": True,
                    "briefing_id": updated_briefing.id,
                    "question_number": current_question,
                    "next_question": None,
                    "completed": False,
                    "status": updated_briefing.status.value,
                }

            # Commit all changes before attempting WhatsApp send
            await self.db_session.commit()
            logger.debug(f"DB changes committed for webhook {wa_message_id}")

            # ====================================================================
            # Record processing BEFORE WhatsApp send (for idempotency on retry)
            # ====================================================================
            # Mark webhook as processed immediately after commit but before WhatsApp.
            # On retry after WhatsApp failure, this prevents re-processing the answer
            # while still allowing the WhatsApp send to be retried.
            await self._record_processed_webhook(wa_message_id, result_data)

            # ====================================================================
            # POST-COMMIT: Send WhatsApp messages (OUTSIDE transaction)
            # ====================================================================
            # If WhatsApp fails here, exception propagates and webhook retries.
            # On retry, idempotency check above will catch it and skip re-processing.

            if completion_message_needed:
                await self._send_completion_message(client, phone_number_id)
            elif next_question_text:
                await self._send_next_question(
                    client=client,
                    question_text=next_question_text,
                    phone_number_id=phone_number_id,
                )

            return result_data

        except Exception as e:
            # Rollback any uncommitted changes
            await self.db_session.rollback()
            logger.error(f"Error processing client answer, rolled back: {str(e)}", exc_info=True)
            # Re-raise to propagate to webhook caller (trigger retry)
            raise

    async def _find_client_by_phone(self, phone_number: str) -> EndClient | None:
        """Find client by phone number."""
        result = await self.db_session.execute(
            select(EndClient).where(EndClient.phone == phone_number)
        )
        return result.scalar_one_or_none()

    async def _get_or_create_session(
        self,
        client_id: UUID,
        phone_number: str,
        session_id: UUID | None = None,
    ) -> WhatsAppSession:
        """Get existing session or create new one."""
        if session_id:
            result = await self.db_session.execute(
                select(WhatsAppSession).where(WhatsAppSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                return session

        # Try to find active session for this client
        result = await self.db_session.execute(
            select(WhatsAppSession).where(
                WhatsAppSession.end_client_id == client_id,
                WhatsAppSession.status == SessionStatus.ACTIVE.value,
            )
        )
        existing_session = result.scalar_one_or_none()

        if existing_session:
            # Update last interaction timestamp
            existing_session.last_interaction_at = datetime.now()
            await self.db_session.flush()
            return existing_session

        # Create new session
        new_session = WhatsAppSession(
            end_client_id=client_id,
            phone_number=phone_number,
            status=SessionStatus.ACTIVE.value,
        )
        self.db_session.add(new_session)
        await self.db_session.flush()
        logger.info(f"Created new WhatsApp session {new_session.id} for client {client_id}")
        return new_session

    async def _save_incoming_message(
        self,
        session_id: UUID,
        wa_message_id: str,
        answer_text: str,
    ) -> WhatsAppMessage:
        """Save incoming message to database (idempotent).

        If message with this wa_message_id already exists (from previous webhook attempt),
        returns the existing message instead of creating a duplicate. This allows webhook
        retries to proceed after WhatsApp send failures.

        Args:
            session_id: WhatsApp session ID
            wa_message_id: WhatsApp message ID (unique)
            answer_text: Message text content

        Returns:
            WhatsAppMessage (existing or newly created)
        """
        # Check if message already exists (idempotency for webhook retries)
        result = await self.db_session.execute(
            select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == wa_message_id)
        )
        existing_message = result.scalar_one_or_none()

        if existing_message:
            logger.debug(
                f"Message {wa_message_id} already exists (webhook retry), reusing existing record"
            )
            return existing_message

        # Create new message
        message = WhatsAppMessage(
            session_id=session_id,
            wa_message_id=wa_message_id,
            direction=MessageDirection.INBOUND.value,
            status=MessageStatus.RECEIVED.value,
            content={
                "type": "text",
                "text": {"body": answer_text},
            },
            timestamp=datetime.now(),
        )
        self.db_session.add(message)
        await self.db_session.flush()
        logger.debug(f"Saved new incoming message {wa_message_id}")
        return message

    async def _find_active_briefing(self, client_id: UUID) -> Briefing | None:
        """Find active briefing for client."""
        result = await self.db_session.execute(
            select(Briefing).where(
                Briefing.end_client_id == client_id,
                Briefing.status == BriefingStatus.IN_PROGRESS,
            )
        )
        return result.scalar_one_or_none()

    async def _should_complete_briefing(self, briefing: Briefing) -> bool:
        """Check if briefing should be completed (all required questions answered)."""
        # Get template version to check required questions
        result = await self.db_session.execute(
            select(TemplateVersion).where(TemplateVersion.id == briefing.template_version_id)
        )
        template_version = result.scalar_one_or_none()
        if not template_version:
            return False

        # Get all required questions
        required_questions = [
            q["order"] for q in template_version.questions if q.get("required", False)
        ]

        # Get answered questions
        answered_questions = [int(k) for k in (briefing.answers or {}).keys()]

        # Check if all required questions are answered
        all_required_answered = all(q in answered_questions for q in required_questions)

        # Get next question
        next_question = await self.orchestrator.next_question(briefing.id)

        # Complete if all required are answered AND (no more questions OR next is optional)
        if all_required_answered:
            if not next_question:
                # No more questions at all
                return True
            # Check if remaining questions are optional
            next_is_optional = not next_question.get("required", False)
            if next_is_optional:
                # Can complete now or wait for optional answers
                # Complete if no more questions after this optional one
                total_questions = len(template_version.questions)
                if briefing.current_question_order >= total_questions:
                    return True

        return False

    async def _send_next_question(
        self,
        client: EndClient,
        question_text: str,
        phone_number_id: str | None = None,
    ) -> None:
        """Send next question to client via WhatsApp."""
        # Get organization to access WhatsApp credentials
        result = await self.db_session.execute(
            select(Organization)
            .join(Architect, Organization.id == Architect.organization_id)
            .join(EndClient, Architect.id == EndClient.architect_id)
            .where(EndClient.id == client.id)
        )
        organization = result.scalar_one_or_none()

        if not organization:
            logger.error(f"Organization not found for client {client.id}")
            return

        # Get WhatsApp config with decrypted token
        account_service = WhatsAppAccountService(self.db_session)
        config = await account_service.get_account_config(organization.id)

        if not config:
            logger.error("WhatsApp credentials not configured")
            return

        # Send message
        whatsapp_service = WhatsAppService(
            phone_number_id=config.phone_number_id,
            access_token=config.access_token,  # Already decrypted
        )

        result = await whatsapp_service.send_text_message(
            to=client.phone,
            text=question_text,
        )

        if result.get("success"):
            logger.info(f"Sent next question to {client.phone}")
        else:
            logger.error(f"Failed to send next question: {result.get('error')}")

    async def _send_completion_message(
        self,
        client: EndClient,
        phone_number_id: str | None = None,
    ) -> None:
        """Send completion message to client."""
        completion_message = (
            f"Obrigado, {client.name}! ✅\n\n"
            "Seu briefing foi concluído com sucesso. "
            "Nossa equipe irá analisar suas respostas e entrar em contato em breve."
        )

        # Get organization
        result = await self.db_session.execute(
            select(Organization)
            .join(Architect, Organization.id == Architect.organization_id)
            .join(EndClient, Architect.id == EndClient.architect_id)
            .where(EndClient.id == client.id)
        )
        organization = result.scalar_one_or_none()

        if not organization:
            return

        # Get WhatsApp config with decrypted token
        account_service = WhatsAppAccountService(self.db_session)
        config = await account_service.get_account_config(organization.id)

        if not config:
            return

        whatsapp_service = WhatsAppService(
            phone_number_id=config.phone_number_id,
            access_token=config.access_token,  # Already decrypted
        )

        await whatsapp_service.send_text_message(
            to=client.phone,
            text=completion_message,
        )

    async def _send_no_active_briefing_message(
        self,
        client: EndClient,
        phone_number_id: str | None = None,
    ) -> None:
        """Send message when client has no active briefing."""
        message = (
            f"Olá, {client.name}! 👋\n\n"
            "No momento, você não tem um briefing ativo. "
            "Entre em contato com seu arquiteto para iniciar um novo briefing."
        )

        # Get organization
        result = await self.db_session.execute(
            select(Organization)
            .join(Architect, Organization.id == Architect.organization_id)
            .join(EndClient, Architect.id == EndClient.architect_id)
            .where(EndClient.id == client.id)
        )
        organization = result.scalar_one_or_none()

        if not organization:
            return

        # Get WhatsApp config with decrypted token
        account_service = WhatsAppAccountService(self.db_session)
        config = await account_service.get_account_config(organization.id)

        if not config:
            return

        whatsapp_service = WhatsAppService(
            phone_number_id=config.phone_number_id,
            access_token=config.access_token,  # Already decrypted
        )

        await whatsapp_service.send_text_message(
            to=client.phone,
            text=message,
        )

    async def _check_if_webhook_already_processed(
        self, wa_message_id: str
    ) -> ProcessedWebhook | None:
        """Check if webhook has already been processed (idempotency).

        Args:
            wa_message_id: WhatsApp message ID

        Returns:
            ProcessedWebhook if already processed, None otherwise
        """
        result = await self.db_session.execute(
            select(ProcessedWebhook).where(ProcessedWebhook.wa_message_id == wa_message_id)
        )
        return result.scalar_one_or_none()

    async def _record_processed_webhook(
        self, wa_message_id: str, result_data: dict[str, Any]
    ) -> None:
        """Record that webhook has been successfully processed (idempotency).

        Args:
            wa_message_id: WhatsApp message ID
            result_data: Processing result to cache (will be JSON serialized)
        """
        # Convert UUIDs to strings for JSON serialization
        serializable_data = result_data.copy()
        if "briefing_id" in serializable_data:
            serializable_data["briefing_id"] = str(serializable_data["briefing_id"])

        processed_webhook = ProcessedWebhook(
            wa_message_id=wa_message_id,
            result_data=serializable_data,
        )
        self.db_session.add(processed_webhook)
        await self.db_session.commit()
        logger.debug(f"Recorded processed webhook {wa_message_id}")
