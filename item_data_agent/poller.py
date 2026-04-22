"""Background polling service for inbound emails."""
import asyncio
from typing import Optional, Callable, Awaitable

from item_data_agent.email_client import EmailClient
from item_data_agent.imap_client import IMAPClient


class EmailPoller:
    """Background service that polls for inbound emails."""
    
    def __init__(self, email_client: EmailClient, imap_client: IMAPClient, interval: int = 30,
                 reply_handler: Optional[Callable[[dict], Awaitable[None]]] = None):
        """Initialize the email poller.
        
        Args:
            email_client: Email client instance
            imap_client: IMAP client instance for reading inbox
            interval: Polling interval in seconds (default: 30)
            reply_handler: Optional async function to handle inbound replies
        """
        self.email_client = email_client
        self.imap_client = imap_client
        self.interval = interval
        self.reply_handler = reply_handler
        self.running = False
        self.task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the polling service."""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._poll_loop())
        print(f"Email polling started (interval: {self.interval}s)")
    
    async def stop(self):
        """Stop the polling service."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        print("Email polling stopped")
    
    async def _poll_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                # Poll IMAP inbox for new messages
                new_messages = await self.imap_client.poll_inbox()
                
                if new_messages:
                    print(f"\n� {len(new_messages)} new email(s) from inbox")
                    for msg in new_messages:
                        # Process through email client for threading
                        self.email_client.process_inbound_webhook(msg)
                        
                        # Trigger agent workflow to process the reply
                        if self.reply_handler:
                            await self.reply_handler(msg)
                
                # Wait before next poll
                await asyncio.sleep(self.interval)
                
            except Exception as e:
                print(f"Error in polling loop: {e}")
                await asyncio.sleep(self.interval)
