"""SMTP email client for sending emails without Postmark."""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid

from item_data_agent.config import settings
from item_data_agent.email_client import InMemoryThreadStore


class SMTPClient(InMemoryThreadStore):
    """Client for outbound email via SMTP with shared in-memory threading."""

    def __init__(self) -> None:
        super().__init__()
        self.server = settings.smtp_server
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.from_email = settings.smtp_from_email
        self.use_ssl = settings.smtp_use_ssl
        self.starttls = settings.smtp_starttls

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> str:
        """Send an email through SMTP and return canonical thread ID."""
        message_id = make_msgid()

        message = EmailMessage()
        message["From"] = self.from_email
        message["To"] = to
        message["Subject"] = subject
        message["Message-ID"] = message_id

        if thread_id:
            formatted_thread_id = (
                thread_id if str(thread_id).startswith("<") else f"<{thread_id}>"
            )
            message["In-Reply-To"] = formatted_thread_id
            message["References"] = formatted_thread_id

        message.set_content(body)

        await asyncio.to_thread(self._send_blocking, message)

        if thread_id:
            canonical_thread_id = self.normalize_message_ref(thread_id) or thread_id
        else:
            canonical_thread_id = self.normalize_message_ref(message_id) or message_id

        self.register_outbound_message(
            message_id=message_id,
            thread_id=canonical_thread_id,
            from_email=self.from_email,
            to_email=to,
            subject=subject,
            body=body,
        )
        return canonical_thread_id

    def _send_blocking(self, message: EmailMessage) -> None:
        """Send SMTP email in a blocking context."""
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.server, self.port, timeout=30) as smtp:
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(self.server, self.port, timeout=30) as smtp:
            smtp.ehlo()
            if self.starttls:
                smtp.starttls()
                smtp.ehlo()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(message)
