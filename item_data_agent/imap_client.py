"""IMAP email client for receiving supplier responses."""
import asyncio
from typing import Any
from datetime import datetime
import email
from email.header import decode_header
from imap_tools import MailBox, AND
from imap_tools.message import MailMessage

from item_data_agent.config import settings


class IMAPClient:
    """Client for checking email inbox via IMAP."""
    
    def __init__(self):
        """Initialize the IMAP client."""
        self.server = settings.imap_server
        self.port = settings.imap_port
        self.username = settings.imap_username
        self.password = settings.imap_password
        self.use_ssl = settings.imap_use_ssl
        self.processed_message_ids: set[str] = set()
    
    async def poll_inbox(self) -> list[dict[str, Any]]:
        """Poll the inbox for new messages.
        
        Returns:
            List of new email messages
        """
        # Run in thread pool since imap_tools is synchronous
        return await asyncio.to_thread(self._fetch_messages)
    
    def _fetch_messages(self) -> list[dict[str, Any]]:
        """Fetch messages from inbox (synchronous).
        
        Returns:
            List of new message dictionaries
        """
        new_messages = []
        
        try:
            print(f"IMAP connecting to {self.server}:{self.port} as {self.username}")
            with MailBox(self.server, self.port).login(self.username, self.password) as mailbox:
                print("IMAP connected successfully")
                # Get unread messages
                for msg in mailbox.fetch(AND(seen=False), mark_seen=False, limit=50):
                    message_id = msg.uid
                    
                    # Skip if already processed
                    if message_id in self.processed_message_ids:
                        continue
                    
                    # Mark as processed
                    self.processed_message_ids.add(message_id)
                    
                    # Extract message data
                    message_data = {
                        "MessageID": message_id,
                        "From": msg.from_,
                        "To": msg.to[0] if msg.to else "",
                        "Subject": msg.subject,
                        "TextBody": msg.text or "",
                        "HtmlBody": msg.html or "",
                        "Headers": self._extract_headers(msg),
                        "Attachments": self._extract_attachments(msg),
                        "ReceivedAt": msg.date.isoformat() if msg.date else datetime.now().isoformat()
                    }
                    
                    new_messages.append(message_data)
                    
                    # Mark as read so we don't process again
                    mailbox.flag(msg.uid, ['\\SEEN'], True)
            
            print(f"IMAP fetch complete: {len(new_messages)} new message(s)")
            return new_messages


        except Exception as e:
            print(f"Error fetching IMAP messages: {e}")
            return []
    
    def _extract_headers(self, msg: MailMessage) -> list[dict[str, str]]:
        """Extract relevant headers from email message.
        
        Args:
            msg: Mail message object
            
        Returns:
            List of header dictionaries
        """
        headers = []
        
        # Get the raw headers we care about
        header_names = ["In-Reply-To", "References", "Message-ID"]
        
        for header_name in header_names:
            value = msg.headers.get(header_name.lower())
            if value:
                # Handle different value types (string, list, tuple)
                if isinstance(value, (list, tuple)):
                    value = value[0] if value else None
                
                if value:
                    headers.append({
                        "Name": header_name,
                        "Value": str(value)
                    })
        
        return headers
    
    def _extract_attachments(self, msg: MailMessage) -> list[dict[str, Any]]:
        """Extract attachments from email message.
        
        Args:
            msg: Mail message object
            
        Returns:
            List of attachment dictionaries with metadata and content
        """
        attachments = []
        
        for att in msg.attachments:
            attachment_data = {
                "Name": att.filename,
                "ContentType": att.content_type,
                "ContentLength": len(att.payload),
                "Content": att.payload,  # bytes
                "ContentID": att.content_id if hasattr(att, 'content_id') else None
            }
            attachments.append(attachment_data)
        
        return attachments
