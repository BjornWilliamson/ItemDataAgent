"""Provider-agnostic email client interfaces and shared logic."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class EmailClient(Protocol):
    """Protocol for outbound/inbound email operations used by the agent."""

    message_to_thread: dict[str, str]

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> str:
        """Send an email and return canonical thread ID."""

    async def get_new_thread_messages(
        self,
        thread_id: str,
        processed_ids: set[str],
    ) -> list[dict[str, Any]]:
        """Return inbound messages in thread that are not yet processed."""

    def process_inbound_webhook(self, webhook_data: dict[str, Any]) -> None:
        """Normalize/store inbound message payload regardless of provider."""

    def get_thread_attachments(self, thread_id: str) -> list[dict[str, Any]]:
        """Return attachments for all inbound messages in a thread."""


class InMemoryThreadStore:
    """Shared in-memory thread/message tracking for email providers."""

    def __init__(self) -> None:
        self.received_emails: dict[str, list[dict[str, Any]]] = {}
        self.processed_message_ids: set[str] = set()
        self.message_to_thread: dict[str, str] = {}

    @staticmethod
    def normalize_message_ref(value: str | None) -> str | None:
        """Normalize RFC message refs for stable matching.

        Examples:
        - "<abc@domain>" -> "abc"
        - "abc@domain" -> "abc"
        - "abc" -> "abc"
        """
        if not value:
            return None
        normalized = str(value).strip().strip("<>")
        if "@" in normalized:
            normalized = normalized.split("@", 1)[0]
        return normalized or None

    def register_outbound_message(
        self,
        *,
        message_id: str,
        thread_id: str,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
    ) -> None:
        """Store outbound message and link all known IDs to canonical thread."""
        if thread_id not in self.received_emails:
            self.received_emails[thread_id] = []

        self.received_emails[thread_id].append(
            {
                "message_id": message_id,
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "body": body,
                "direction": "outbound",
                "timestamp": datetime.now().isoformat(),
            }
        )

        self.message_to_thread[message_id] = thread_id
        normalized_message_id = self.normalize_message_ref(message_id)
        if normalized_message_id:
            self.message_to_thread[normalized_message_id] = thread_id

    async def get_new_thread_messages(
        self,
        thread_id: str,
        processed_ids: set[str],
    ) -> list[dict[str, Any]]:
        """Get inbound messages not yet processed by message ID."""
        messages = self.received_emails.get(thread_id, [])
        inbound_messages = [m for m in messages if m.get("direction") == "inbound"]

        new_messages = [
            msg for msg in inbound_messages if msg["message_id"] not in processed_ids
        ]

        return [
            {
                "from": msg["from"],
                "body": msg["body"],
                "attachments": msg.get("attachments", []),
                "id": msg["message_id"],
            }
            for msg in new_messages
        ]

    def process_inbound_webhook(self, webhook_data: dict[str, Any]) -> None:
        """Process normalized inbound payload and attach to canonical thread."""
        message_id = str(webhook_data.get("MessageID", ""))
        from_email = webhook_data.get("From", "")
        to_email = webhook_data.get("To", "")
        subject = webhook_data.get("Subject", "")
        text_body = webhook_data.get("TextBody", "")
        html_body = webhook_data.get("HtmlBody", "")
        attachments = webhook_data.get("Attachments", [])

        headers = webhook_data.get("Headers", [])
        in_reply_to = None
        references = None

        for header in headers:
            if header.get("Name") == "In-Reply-To":
                in_reply_to = header.get("Value")
            elif header.get("Name") == "References":
                references = header.get("Value")

        if isinstance(in_reply_to, (list, tuple)):
            in_reply_to = in_reply_to[0] if in_reply_to else None
        if isinstance(references, (list, tuple)):
            references = references[0] if references else None

        reference = in_reply_to or (references.split()[0] if references else message_id)
        normalized_reference = self.normalize_message_ref(str(reference))

        thread_id = self.message_to_thread.get(str(reference), normalized_reference)
        if thread_id:
            thread_id = self.message_to_thread.get(thread_id, thread_id)

        if not thread_id:
            # New inbound thread if we cannot map to an existing conversation.
            thread_id = self.normalize_message_ref(message_id) or message_id

        if thread_id not in self.received_emails:
            self.received_emails[thread_id] = []

        self.received_emails[thread_id].append(
            {
                "message_id": message_id,
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "body": text_body or html_body,
                "attachments": attachments,
                "direction": "inbound",
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_thread_attachments(self, thread_id: str) -> list[dict[str, Any]]:
        """Get all inbound attachments from a thread with metadata."""
        messages = self.received_emails.get(thread_id, [])
        all_attachments = []

        for msg in messages:
            if msg.get("direction") == "inbound":
                for att in msg.get("attachments", []):
                    all_attachments.append(
                        {
                            "filename": att.get("Name"),
                            "content_type": att.get("ContentType"),
                            "size": att.get("ContentLength"),
                            "content": att.get("Content"),
                            "message_from": msg.get("from"),
                            "timestamp": msg.get("timestamp"),
                        }
                    )

        return all_attachments
