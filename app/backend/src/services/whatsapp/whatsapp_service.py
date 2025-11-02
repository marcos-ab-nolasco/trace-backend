"""WhatsApp Business Cloud API service for sending messages."""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for sending messages via WhatsApp Business Cloud API."""

    GRAPH_API_VERSION = "v18.0"
    BASE_URL = "https://graph.facebook.com"
    MAX_RETRIES = 2

    def __init__(self, phone_number_id: str, access_token: str):
        """
        Initialize WhatsApp service.

        Args:
            phone_number_id: WhatsApp Business phone number ID
            access_token: Access token for WhatsApp Business API
        """
        self.phone_number_id = phone_number_id
        self.access_token = access_token

    def _get_messages_url(self) -> str:
        """Get the messages API endpoint URL."""
        return f"{self.BASE_URL}/{self.GRAPH_API_VERSION}/{self.phone_number_id}/messages"

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _format_phone_number(phone: str) -> str:
        """
        Format phone number for WhatsApp API (remove +, spaces, dashes, parentheses).

        Args:
            phone: Phone number in any format

        Returns:
            Phone number with only digits
        """
        return re.sub(r"[^\d]", "", phone)

    async def _send_request(self, payload: dict[str, Any], retries: int = 0) -> dict[str, Any]:
        """
        Send request to WhatsApp API with retry logic.

        Args:
            payload: Request payload
            retries: Current retry count

        Returns:
            Response dict with success status and data/error
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._get_messages_url(),
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    messages = data.get("messages", [])
                    message_id = messages[0]["id"] if messages else None

                    return {
                        "success": True,
                        "message_id": message_id,
                        "data": data,
                    }
                else:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "Unknown error")
                    logger.error(f"WhatsApp API error: {response.status_code} - {error_message}")

                    return {
                        "success": False,
                        "error": error_message,
                        "status_code": response.status_code,
                    }

        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")

            # Retry on network errors
            if retries < self.MAX_RETRIES:
                logger.info(f"Retrying... (attempt {retries + 1}/{self.MAX_RETRIES})")
                return await self._send_request(payload, retries + 1)

            return {
                "success": False,
                "error": f"Failed after {self.MAX_RETRIES + 1} attempts: {str(e)}",
            }

    async def send_text_message(
        self, to: str, text: str, preview_url: bool = False
    ) -> dict[str, Any]:
        """
        Send a text message.

        Args:
            to: Recipient phone number
            text: Message text
            preview_url: Whether to show URL preview

        Returns:
            Response dict with success status and message_id or error
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone_number(to),
            "type": "text",
            "text": {"body": text, "preview_url": preview_url},
        }

        logger.info(f"Sending text message to {to}")
        return await self._send_request(payload)

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Send a template message.

        Args:
            to: Recipient phone number
            template_name: Template name (must be approved in WhatsApp Manager)
            language_code: Language code (e.g., 'en', 'pt_BR')
            components: Optional template components (parameters, buttons, etc.)

        Returns:
            Response dict with success status and message_id or error
        """
        template_payload: dict[str, Any] = {
            "name": template_name,
            "language": {"code": language_code},
        }

        if components:
            template_payload["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone_number(to),
            "type": "template",
            "template": template_payload,
        }

        logger.info(f"Sending template message '{template_name}' to {to}")
        return await self._send_request(payload)

    async def mark_as_read(self, message_id: str) -> dict[str, Any]:
        """
        Mark a message as read.

        Args:
            message_id: WhatsApp message ID (wamid.*)

        Returns:
            Response dict with success status
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        logger.info(f"Marking message {message_id} as read")
        return await self._send_request(payload)
