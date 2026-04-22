"""Postmark API client for sending and receiving emails."""
import httpx
from typing import Any

from item_data_agent.config import settings
from item_data_agent.email_client import InMemoryThreadStore


class PostmarkClient(InMemoryThreadStore):
    """Client for interacting with Postmark API."""
    
    def __init__(self):
        """Initialize the Postmark client."""
        super().__init__()
        self.api_token = settings.postmark_api_token
        self.from_email = settings.postmark_from_email
        self.base_url = "https://api.postmarkapp.com"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": self.api_token
        }
    
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
                        self.register_outbound_message(
                            message_id=message_id,
                            thread_id=thread_id,
                            from_email=self.from_email,
                            to_email=to,
                            subject=subject,
                            body=body,
                        )
                        return thread_id
                    else:
                        # New thread - use message ID as thread ID
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
        since_count: int = 0,
    ) -> list[dict[str, Any]]:
        """Get inbound messages from a thread by count offset (legacy)."""
        messages = self.received_emails.get(thread_id, [])
        inbound = [m for m in messages if m.get("direction") == "inbound"]
        return [
            {
                "from": msg["from"],
                "body": msg["body"],
                "attachments": msg.get("attachments", []),
                "id": msg["message_id"],
            }
            for msg in inbound[since_count:]
        ]
    
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
