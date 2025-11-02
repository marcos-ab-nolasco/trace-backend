"""WhatsApp webhook handler for parsing incoming messages and events."""

import logging
from typing import Any

from src.db.models.whatsapp_message import MessageDirection, MessageStatus

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handler for WhatsApp webhook events."""

    @staticmethod
    def parse_webhook_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Parse WhatsApp webhook payload and extract relevant events.

        Args:
            payload: Raw webhook payload from WhatsApp

        Returns:
            List of parsed events (messages and status updates)
        """
        events: list[dict[str, Any]] = []

        # Validate basic structure
        if payload.get("object") != "whatsapp_business_account":
            logger.warning(f"Invalid webhook object type: {payload.get('object')}")
            return events

        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                if change.get("field") != "messages":
                    continue

                value = change.get("value", {})
                phone_number_id = value.get("metadata", {}).get("phone_number_id")

                # Parse incoming messages
                messages = value.get("messages", [])
                for message in messages:
                    parsed_message = WebhookHandler._parse_message(message, phone_number_id)
                    if parsed_message:
                        events.append(parsed_message)

                # Parse status updates
                statuses = value.get("statuses", [])
                for status in statuses:
                    parsed_status = WebhookHandler._parse_status_update(status, phone_number_id)
                    if parsed_status:
                        events.append(parsed_status)

        return events

    @staticmethod
    def _parse_message(
        message: dict[str, Any], phone_number_id: str | None
    ) -> dict[str, Any] | None:
        """
        Parse an incoming message.

        Args:
            message: Message object from webhook
            phone_number_id: WhatsApp phone number ID

        Returns:
            Parsed message dict or None if unsupported
        """
        message_id = message.get("id")
        from_number = message.get("from")
        timestamp = message.get("timestamp")
        message_type = message.get("type")

        if not all([message_id, from_number, message_type]):
            logger.warning(f"Incomplete message data: {message}")
            return None

        # Parse content based on message type
        content: dict[str, Any] = {"type": message_type}

        if message_type == "text":
            text_body = message.get("text", {}).get("body")
            if text_body:
                content["text"] = {"body": text_body}
        elif message_type == "image":
            image_data = message.get("image", {})
            content["image"] = image_data
        elif message_type == "document":
            document_data = message.get("document", {})
            content["document"] = document_data
        elif message_type == "audio":
            audio_data = message.get("audio", {})
            content["audio"] = audio_data
        elif message_type == "video":
            video_data = message.get("video", {})
            content["video"] = video_data
        else:
            logger.info(f"Unsupported message type: {message_type}")
            content["unsupported"] = True

        return {
            "event_type": "message",
            "wa_message_id": message_id,
            "from": from_number,
            "phone_number_id": phone_number_id,
            "timestamp": timestamp,
            "direction": MessageDirection.INBOUND.value,
            "status": MessageStatus.RECEIVED.value,
            "content": content,
        }

    @staticmethod
    def _parse_status_update(
        status: dict[str, Any], phone_number_id: str | None
    ) -> dict[str, Any] | None:
        """
        Parse a message status update.

        Args:
            status: Status object from webhook
            phone_number_id: WhatsApp phone number ID

        Returns:
            Parsed status update dict or None if invalid
        """
        message_id = status.get("id")
        status_value = status.get("status")
        timestamp = status.get("timestamp")
        recipient_id = status.get("recipient_id")

        if not all([message_id, status_value]):
            logger.warning(f"Incomplete status data: {status}")
            return None

        # Map WhatsApp status to our MessageStatus enum
        status_mapping = {
            "sent": MessageStatus.SENT.value,
            "delivered": MessageStatus.DELIVERED.value,
            "read": MessageStatus.READ.value,
            "failed": MessageStatus.FAILED.value,
        }

        mapped_status = status_mapping.get(status_value, status_value)

        result: dict[str, Any] = {
            "event_type": "status_update",
            "wa_message_id": message_id,
            "status": mapped_status,
            "timestamp": timestamp,
            "phone_number_id": phone_number_id,
            "recipient_id": recipient_id,
        }

        # Include error details if failed
        if status_value == "failed":
            errors = status.get("errors", [])
            if errors:
                error = errors[0]  # Take first error
                result["error_code"] = str(error.get("code", ""))
                result["error_message"] = error.get("title", "Unknown error")

        return result
