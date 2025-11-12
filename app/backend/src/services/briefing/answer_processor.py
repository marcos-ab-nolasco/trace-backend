"""Service for processing client answers received via WhatsApp."""

import logging
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

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

    def _detect_special_command(self, answer_text: str) -> dict[str, Any] | None:
        """Detect special commands in answer text.

        Recognizes commands: pular/pula, voltar, não sei/nao sei
        Commands must be standalone (not mixed with other text).

        Args:
            answer_text: The answer text from user

        Returns:
            dict with command info {"command": "pular"|"voltar"|"não sei"}, or None if not a command
        """
        normalized = answer_text.strip().lower()

        # Command must be standalone (no other text)
        if not re.match(r"^[a-záàâãéêíóôõúç\s]+$", normalized):
            return None

        # Pular command and variants
        if normalized in ["pular", "pula", "skip"]:
            return {"command": "pular"}

        # Voltar command
        if normalized in ["voltar", "volta"]:
            return {"command": "voltar"}

        # Não sei command and variants
        if normalized in ["não sei", "nao sei", "n sei", "ñ sei"]:
            return {"command": "não sei"}

        return None

    async def _validate_answer(
        self, answer_text: str, question: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Validate answer against question type and validation rules.

        Args:
            answer_text: The answer text
            question: Question dict from template

        Returns:
            dict with error {"error": str, "message": str} or success with normalized answer
            {"normalized_answer": str}, or None if validation passes with original answer
        """
        question_type = question.get("type", "text")

        # Number validation
        if question_type == "number":
            # Remove formatting (dots, commas, spaces)
            cleaned = re.sub(r"[.,\s]", "", answer_text)
            if not cleaned.isdigit():
                return {
                    "success": False,
                    "error": "validation_error",
                    "message": "Por favor, envie um número válido para esta pergunta.",
                }

        # Multiple choice validation
        elif question_type == "multiple_choice":
            options = question.get("options", [])
            if not options:
                return None  # No options defined, accept anything

            # Case-insensitive match
            answer_lower = answer_text.lower().strip()
            matched_option = None

            for option in options:
                option_lower = option.lower()
                # Exact match or partial match (at least 3 chars)
                if answer_lower == option_lower or (
                    len(answer_lower) >= 3 and answer_lower in option_lower
                ):
                    matched_option = option
                    break

            if not matched_option:
                options_text = ", ".join(options)
                return {
                    "success": False,
                    "error": "validation_error",
                    "message": f"Opção inválida. Escolha uma das opções válidas: {options_text}",
                }

            # Return normalized answer (correct case from option)
            return {"normalized_answer": matched_option}

        return None

    async def _handle_pular_command(
        self, briefing: Briefing, session: WhatsAppSession, current_question: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle 'pular' command to skip optional questions.

        Args:
            briefing: Current briefing
            session: WhatsApp session
            current_question: Current question dict

        Returns:
            Result dict with success status
        """
        # Check if question is required
        if current_question.get("required", False):
            return {
                "success": False,
                "error": "cannot_skip_required",
                "message": "Esta pergunta é obrigatória e não pode ser pulada. Por favor, responda.",
            }

        # Skip to next question
        briefing.current_question_order += 1
        session.current_question_index += 1
        await self.db_session.flush()

        logger.info(
            f"Skipped optional question {current_question['order']} " f"for briefing {briefing.id}"
        )

        return {"success": True, "command_executed": "pular"}

    async def _handle_voltar_command(
        self, briefing: Briefing, session: WhatsAppSession
    ) -> dict[str, Any]:
        """Handle 'voltar' command to go back to previous question.

        Args:
            briefing: Current briefing
            session: WhatsApp session

        Returns:
            Result dict with success status
        """
        # Check if at first question
        if briefing.current_question_order <= 1:
            return {
                "success": False,
                "error": "cannot_go_back",
                "message": "Você já está na primeira pergunta. Não é possível voltar.",
            }

        # Go back to previous question
        briefing.current_question_order -= 1
        session.current_question_index -= 1
        await self.db_session.flush()

        logger.info(
            f"Went back to question {briefing.current_question_order} "
            f"for briefing {briefing.id}"
        )

        return {"success": True, "command_executed": "voltar"}

    async def _handle_nao_sei_command(
        self, briefing: Briefing, session: WhatsAppSession, current_question: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle 'não sei' command.

        For required questions: save "não sei" as answer and progress
        For optional questions: skip question without saving

        Args:
            briefing: Current briefing
            session: WhatsApp session
            current_question: Current question dict

        Returns:
            Result dict with success status
        """
        question_order = current_question["order"]
        is_required = current_question.get("required", False)

        if is_required:
            # Save "não sei" as the answer for required questions
            if briefing.answers is None:
                briefing.answers = {}
            briefing.answers[str(question_order)] = "não sei"
            # Mark JSONB field as modified (SQLAlchemy doesn't auto-detect dict changes)
            flag_modified(briefing, "answers")

        # Progress to next question (for both required and optional)
        briefing.current_question_order += 1
        session.current_question_index += 1
        await self.db_session.flush()

        logger.info(
            f"Handled 'não sei' for question {question_order} "
            f"(required={is_required}) for briefing {briefing.id}"
        )

        return {"success": True, "command_executed": "não sei"}

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
        client = await self._find_client_by_phone(phone_number)
        if not client:
            logger.warning(f"Client not found for phone {phone_number}")
            return {
                "success": False,
                "error": "client_not_found",
                "message": "Cliente não encontrado no sistema.",
            }

        existing_webhook = await self._check_if_webhook_already_processed(wa_message_id)
        if existing_webhook:
            logger.info(
                f"Webhook {wa_message_id} already processed, attempting WhatsApp retry if needed"
            )
            cached_result = existing_webhook.result_data or {
                "success": True,
                "message": "Already processed (idempotent)",
            }

            try:
                if cached_result.get("completed"):
                    await self._send_completion_message(client, phone_number_id)
                elif cached_result.get("next_question"):
                    await self._send_next_question(
                        client=client,
                        question_text=cached_result["next_question"],
                        phone_number_id=phone_number_id,
                    )
                logger.info(f"WhatsApp retry successful for webhook {wa_message_id}")
            except Exception as e:
                logger.error(f"WhatsApp retry failed for webhook {wa_message_id}: {e}")
                raise

            return cached_result

        active_briefing = await self._find_active_briefing(client.id)
        if not active_briefing:
            logger.warning(f"No active briefing for client {client.id}")
            await self._send_no_active_briefing_message(client, phone_number_id)
            return {
                "success": False,
                "error": "no_active_briefing",
                "message": "Nenhum briefing ativo encontrado para este cliente.",
                "no_active_briefing": True,
            }

        next_question_text: str | None = None
        completion_message_needed = False
        result_data: dict[str, Any] = {}

        try:
            logger.debug(f"Starting DB operations for webhook {wa_message_id}")

            wa_session = await self._get_or_create_session(
                client_id=client.id,
                phone_number=phone_number,
                session_id=session_id,
            )

            await self._save_incoming_message(
                session_id=wa_session.id,
                wa_message_id=wa_message_id,
                answer_text=answer_text,
            )

            if wa_session.briefing_id != active_briefing.id:
                # Session is being re-linked to a different briefing
                # Reset question index only if previous briefing was finalized
                if wa_session.briefing_id:
                    old_briefing_result = await self.db_session.execute(
                        select(Briefing).where(Briefing.id == wa_session.briefing_id)
                    )
                    old_briefing = old_briefing_result.scalar_one_or_none()

                    if old_briefing and old_briefing.status in [
                        BriefingStatus.COMPLETED,
                        BriefingStatus.CANCELLED,
                    ]:
                        wa_session.current_question_index = 1
                        logger.info(
                            f"Reset session {wa_session.id} question index to 1 "
                            f"(previous briefing {old_briefing.id} was {old_briefing.status.value})"
                        )

                wa_session.briefing_id = active_briefing.id
                await self.db_session.flush()

            # Get current question from template
            template_result = await self.db_session.execute(
                select(TemplateVersion).where(
                    TemplateVersion.id == active_briefing.template_version_id
                )
            )
            template_version = template_result.scalar_one()
            current_question_order = active_briefing.current_question_order

            current_question_data = next(
                (q for q in template_version.questions if q["order"] == current_question_order),
                None,
            )

            if not current_question_data:
                raise ValueError(f"Question {current_question_order} not found in template")

            # Detect special commands
            command_detected = self._detect_special_command(answer_text)

            if command_detected:
                command = command_detected["command"]
                logger.info(f"Detected command '{command}' for briefing {active_briefing.id}")

                # Execute command
                if command == "pular":
                    command_result = await self._handle_pular_command(
                        active_briefing, wa_session, current_question_data
                    )
                elif command == "voltar":
                    command_result = await self._handle_voltar_command(active_briefing, wa_session)
                elif command == "não sei":
                    command_result = await self._handle_nao_sei_command(
                        active_briefing, wa_session, current_question_data
                    )
                else:
                    command_result = {"success": False, "error": "unknown_command"}

                # If command failed, return error immediately
                if not command_result.get("success"):
                    await self.db_session.rollback()
                    return command_result

                # Command succeeded - determine next action
                await self.db_session.refresh(active_briefing)

                next_question_data = await self.orchestrator.get_next_question_for_session(
                    session_id=wa_session.id,
                    template_version_id=active_briefing.template_version_id,
                )

                should_complete = await self._should_complete_briefing(active_briefing)

                if should_complete:
                    completed_briefing = await self.orchestrator.complete_briefing(
                        active_briefing.id, auto_commit=False
                    )
                    result_data = {
                        **command_result,
                        "briefing_id": completed_briefing.id,
                        "question_number": current_question_order,
                        "next_question": None,
                        "completed": True,
                        "status": BriefingStatus.COMPLETED.value,
                    }
                    completion_message_needed = True
                elif next_question_data:
                    next_question_text = next_question_data["question"]
                    result_data = {
                        **command_result,
                        "briefing_id": active_briefing.id,
                        "question_number": current_question_order,
                        "next_question": next_question_text,
                        "completed": False,
                        "status": active_briefing.status.value,
                    }
                else:
                    result_data = {
                        **command_result,
                        "briefing_id": active_briefing.id,
                        "question_number": current_question_order,
                        "next_question": None,
                        "completed": False,
                        "status": active_briefing.status.value,
                    }

                await self.db_session.commit()
                await self._record_processed_webhook(wa_message_id, result_data)

                if completion_message_needed:
                    await self._send_completion_message(client, phone_number_id)
                elif next_question_text:
                    await self._send_next_question(
                        client=client,
                        question_text=next_question_text,
                        phone_number_id=phone_number_id,
                    )

                return result_data

            # Not a command - validate answer
            validation_result = await self._validate_answer(answer_text, current_question_data)

            if validation_result and "error" in validation_result:
                logger.warning(
                    f"Validation failed for briefing {active_briefing.id}: "
                    f"{validation_result['message']}"
                )
                # Record webhook even for validation errors (idempotency)
                await self._record_processed_webhook(wa_message_id, validation_result)
                return validation_result

            # Validation passed - use normalized answer if provided (e.g., for multiple_choice)
            answer_to_save = answer_text
            if validation_result and "normalized_answer" in validation_result:
                answer_to_save = validation_result["normalized_answer"]

            # Process answer normally
            current_question = active_briefing.current_question_order
            updated_briefing = await self.orchestrator.process_answer(
                briefing_id=active_briefing.id,
                question_order=current_question,
                answer=answer_to_save,
                auto_commit=False,
                session_id=wa_session.id,
            )

            logger.info(
                f"Processed answer for briefing {active_briefing.id}, question {current_question}"
            )

            next_question_data = await self.orchestrator.get_next_question_for_session(
                session_id=wa_session.id,
                template_version_id=active_briefing.template_version_id,
            )

            should_complete = await self._should_complete_briefing(updated_briefing)

            if should_complete:
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
                result_data = {
                    "success": True,
                    "briefing_id": updated_briefing.id,
                    "question_number": current_question,
                    "next_question": None,
                    "completed": False,
                    "status": updated_briefing.status.value,
                }

            await self.db_session.commit()
            logger.debug(f"DB changes committed for webhook {wa_message_id}")

            await self._record_processed_webhook(wa_message_id, result_data)

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
            await self.db_session.rollback()
            logger.error(f"Error processing client answer, rolled back: {str(e)}", exc_info=True)
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

        result = await self.db_session.execute(
            select(WhatsAppSession).where(
                WhatsAppSession.end_client_id == client_id,
                WhatsAppSession.status == SessionStatus.ACTIVE.value,
            )
        )
        existing_session = result.scalar_one_or_none()

        if existing_session:
            existing_session.last_interaction_at = datetime.now()
            await self.db_session.flush()
            return existing_session

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
        result = await self.db_session.execute(
            select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == wa_message_id)
        )
        existing_message = result.scalar_one_or_none()

        if existing_message:
            logger.debug(
                f"Message {wa_message_id} already exists (webhook retry), reusing existing record"
            )
            return existing_message

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
        result = await self.db_session.execute(
            select(TemplateVersion).where(TemplateVersion.id == briefing.template_version_id)
        )
        template_version = result.scalar_one_or_none()
        if not template_version:
            return False

        required_questions = [
            q["order"] for q in template_version.questions if q.get("required", False)
        ]

        answered_questions = [int(k) for k in (briefing.answers or {}).keys()]

        all_required_answered = all(q in answered_questions for q in required_questions)

        next_question = await self.orchestrator.next_question(briefing.id)

        if all_required_answered:
            if not next_question:
                return True
            next_is_optional = not next_question.get("required", False)
            if next_is_optional:
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

        account_service = WhatsAppAccountService(self.db_session)
        config = await account_service.get_account_config(organization.id)

        if not config:
            logger.error("WhatsApp credentials not configured")
            return

        whatsapp_service = WhatsAppService(
            phone_number_id=config.phone_number_id,
            access_token=config.access_token,
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

        result = await self.db_session.execute(
            select(Organization)
            .join(Architect, Organization.id == Architect.organization_id)
            .join(EndClient, Architect.id == EndClient.architect_id)
            .where(EndClient.id == client.id)
        )
        organization = result.scalar_one_or_none()

        if not organization:
            return

        account_service = WhatsAppAccountService(self.db_session)
        config = await account_service.get_account_config(organization.id)

        if not config:
            return

        whatsapp_service = WhatsAppService(
            phone_number_id=config.phone_number_id,
            access_token=config.access_token,
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

        result = await self.db_session.execute(
            select(Organization)
            .join(Architect, Organization.id == Architect.organization_id)
            .join(EndClient, Architect.id == EndClient.architect_id)
            .where(EndClient.id == client.id)
        )
        organization = result.scalar_one_or_none()

        if not organization:
            return

        account_service = WhatsAppAccountService(self.db_session)
        config = await account_service.get_account_config(organization.id)

        if not config:
            return

        whatsapp_service = WhatsAppService(
            phone_number_id=config.phone_number_id,
            access_token=config.access_token,
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
