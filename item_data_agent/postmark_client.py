"""Postmark API client for sending and receiving emails."""
import httpx
from typing import Any
from datetime import datetime

from item_data_agent.config import settings


class PostmarkClient:
    """Client for interacting with Postmark API."""
    
    def __init__(self):
        """Initialize the Postmark client."""
        self.api_token = settings.postmark_api_token
        self.from_email = settings.postmark_from_email
        self.base_url = "https://api.postmarkapp.com"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": self.api_token
        }
        # In-memory storage for received emails (in production, use a database)
        self.received_emails: dict[str, list[dict[str, Any]]] = {}
        # Track processed message IDs to avoid duplicates
        self.processed_message_ids: set[str] = set()
        # Track sent message IDs to thread mapping
        self.message_to_thread: dict[str, str] = {}
    
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None
    ) -> str:
        """Send an email via Postmark.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body content (HTML or text)
            thread_id: Optional thread ID to reply to existing conversation
            
        Returns:
            Thread ID (Message-ID) of the sent email
        """
        # Build email data
        email_data = {
            "From": self.from_email,
            "To": to,
            "Subject": subject,
            "TextBody": body,
            "MessageStream": "outbound"
        }
        
        # If replying to a thread, add reference headers
        if thread_id:
            # Ensure thread_id has angle brackets for proper email header format
            formatted_thread_id = thread_id if thread_id.startswith('<') else f"<{thread_id}>"
            email_data["Headers"] = [
                {"Name": "In-Reply-To", "Value": formatted_thread_id},
                {"Name": "References", "Value": formatted_thread_id}
            ]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/email",
                    json=email_data,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message_id = result.get("MessageID", "")
                    
                    # Store sent email for thread tracking
                    if thread_id:
                        if thread_id not in self.received_emails:
                            self.received_emails[thread_id] = []
                        self.received_emails[thread_id].append({
                            "message_id": message_id,
                            "from": self.from_email,
                            "to": to,
                            "subject": subject,
                            "body": body,
                            "direction": "outbound",
                            "timestamp": datetime.now().isoformat()
                        })
                        self.message_to_thread[message_id] = thread_id
                        return thread_id
                    else:
                        # New thread - use message ID as thread ID
                        self.received_emails[message_id] = [{
                            "message_id": message_id,
                            "from": self.from_email,
                            "to": to,
                            "subject": subject,
                            "body": body,
                            "direction": "outbound",
                            "timestamp": datetime.now().isoformat()
                        }]
                        self.message_to_thread[message_id] = message_id
                        return message_id
                else:
                    error_msg = response.text
                    print(f"Failed to send email. Status: {response.status_code}, Error: {error_msg}")
                    raise Exception(f"Postmark API error: {error_msg}")
                    
        except httpx.RequestError as e:
            print(f"Error sending email via Postmark: {e}")
            raise
    
    async def get_thread_messages(
        self,
        thread_id: str,
        since_count: int = 0
    ) -> list[dict[str, Any]]:
        """Get inbound messages from a thread by count offset (legacy)."""
        messages = self.received_emails.get(thread_id, [])
        inbound = [m for m in messages if m.get("direction") == "inbound"]
        return [{
            "from": msg["from"],
            "body": msg["body"],
            "attachments": msg.get("attachments", []),
            "id": msg["message_id"]
        } for msg in inbound[since_count:]]

    async def get_new_thread_messages(
        self,
        thread_id: str,
        processed_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Get inbound messages not yet processed, identified by message ID.

        Args:
            thread_id: Thread/Message ID
            processed_ids: Set of already-processed message IDs

        Returns:
            List of new inbound message dictionaries
        """
        messages = self.received_emails.get(thread_id, [])
        inbound_messages = [m for m in messages if m.get("direction") == "inbound"]

        new_messages = [
            msg for msg in inbound_messages
            if msg["message_id"] not in processed_ids
        ]

        return [{
            "from": msg["from"],
            "body": msg["body"],
            "attachments": msg.get("attachments", []),
            "id": msg["message_id"]
        } for msg in new_messages]

    def process_inbound_webhook(self, webhook_data: dict[str, Any]) -> None:
        """Process an inbound email webhook from Postmark.
        
        This should be called by the webhook endpoint when Postmark
        sends an inbound email notification.
        
        Args:
            webhook_data: Webhook payload from Postmark
        """
        # Extract email details from webhook
        message_id = webhook_data.get("MessageID", "")
        from_email = webhook_data.get("From", "")
        to_email = webhook_data.get("To", "")
        subject = webhook_data.get("Subject", "")
        text_body = webhook_data.get("TextBody", "")
        html_body = webhook_data.get("HtmlBody", "")
        attachments = webhook_data.get("Attachments", [])
        
        # Get reference headers to determine thread
        headers = webhook_data.get("Headers", [])
        in_reply_to = None
        references = None
        
        for header in headers:
            if header.get("Name") == "In-Reply-To":
                in_reply_to = header.get("Value")
            elif header.get("Name") == "References":
                references = header.get("Value")
        
        # Ensure values are strings not tuples
        if isinstance(in_reply_to, (list, tuple)):
            in_reply_to = in_reply_to[0] if in_reply_to else None
        if isinstance(references, (list, tuple)):
            references = references[0] if references else None
        
        # Determine thread ID (prefer In-Reply-To, fallback to References, then create new)
        thread_id = in_reply_to or (references.split()[0] if references else message_id)
        thread_id = str(thread_id)  # Ensure it's a string
        
        # Normalize thread ID - remove angle brackets and domain to match state format
        # This ensures consistency: <id@domain> becomes just: id
        thread_id = thread_id.strip('<>')
        if '@' in thread_id:
            thread_id = thread_id.split('@')[0]
        
        print(f"Normalized thread ID for storage: {thread_id}")
        
        # Store the inbound email
        if thread_id not in self.received_emails:
            self.received_emails[thread_id] = []
        
        self.received_emails[thread_id].append({
            "message_id": message_id,
            "from": from_email,
            "to": to_email,
            "subject": subject,
            "body": text_body or html_body,
            "attachments": attachments,
            "direction": "inbound",
            "timestamp": datetime.now().isoformat()
        })
        
        if attachments:
            print(f"Inbound email from {from_email} in thread {thread_id} ({len(attachments)} attachment(s))")
        else:
            print(f"Inbound email from {from_email} in thread {thread_id}")
    
    async def check_new_replies(self, thread_id: str, last_message_id: str) -> bool:
        """Check if there are new replies in a thread.
        
        Args:
            thread_id: Thread/Message ID
            last_message_id: ID of the last processed message
            
        Returns:
            True if there are new messages, False otherwise
        """
        messages = self.received_emails.get(thread_id, [])
        if not messages:
            return False
        
        # Check if the last message ID in thread is different
        return messages[-1]["message_id"] != last_message_id
    
    def get_thread_attachments(self, thread_id: str) -> list[dict[str, Any]]:
        """Get all attachments from a thread.
        
        Args:
            thread_id: Thread/Message ID
            
        Returns:
            List of all attachments from the thread with metadata
        """
        messages = self.received_emails.get(thread_id, [])
        all_attachments = []
        
        for msg in messages:
            if msg.get("direction") == "inbound":
                attachments = msg.get("attachments", [])
                for att in attachments:
                    all_attachments.append({
                        "filename": att.get("Name"),
                        "content_type": att.get("ContentType"),
                        "size": att.get("ContentLength"),
                        "content": att.get("Content"),
                        "message_from": msg.get("from"),
                        "timestamp": msg.get("timestamp")
                    })
        
        return all_attachments
    
    async def poll_inbound_messages(self) -> list[dict[str, Any]]:
        """Poll Postmark for new inbound messages.
        
        This is an alternative to webhooks for testing purposes.
        Checks the inbound message stream for new messages.
        
        Returns:
            List of new inbound message data
        """
        url = f"{self.base_url}/messages/inbound"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params={"count": 50, "offset": 0},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    messages = data.get("InboundMessages", [])
                    
                    new_messages = []
                    for msg in messages:
                        message_id = msg.get("MessageID", "")
                        
                        # Skip if already processed
                        if message_id in self.processed_message_ids:
                            continue
                        
                        # Mark as processed
                        self.processed_message_ids.add(message_id)
                        
                        # Process the message
                        webhook_data = {
                            "MessageID": message_id,
                            "From": msg.get("From", ""),
                            "To": msg.get("To", ""),
                            "Subject": msg.get("Subject", ""),
                            "TextBody": msg.get("TextBody", ""),
                            "HtmlBody": msg.get("HtmlBody", ""),
                            "Headers": msg.get("Headers", [])
                        }
                        
                        self.process_inbound_webhook(webhook_data)
                        new_messages.append(webhook_data)
                    
                    return new_messages
                else:
                    print(f"Failed to poll inbound messages. Status: {response.status_code}")
                    return []
                    
        except httpx.RequestError as e:
            print(f"Error polling inbound messages: {e}")
            return []
