"""FastAPI application for the Item Data Agent."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, EmailStr

from item_data_agent.agent import SupplierAgent
from item_data_agent.postmark_client import PostmarkClient
from item_data_agent.erp_client import ERPClient
from item_data_agent.imap_client import IMAPClient
from item_data_agent.poller import EmailPoller
from item_data_agent.config import settings


# Global instances
postmark_client: PostmarkClient | None = None
erp_client: ERPClient | None = None
imap_client: IMAPClient | None = None
agent: SupplierAgent | None = None
email_poller: EmailPoller | None = None

# Thread ID to item number mapping (in production, use database)
thread_to_item: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global postmark_client, erp_client, imap_client, agent, email_poller
    
    # Startup
    postmark_client = PostmarkClient()
    erp_client = ERPClient()
    imap_client = IMAPClient()
    agent = SupplierAgent(postmark_client, erp_client)
    
    # Start email polling (checks IMAP inbox every 30 seconds)
    email_poller = EmailPoller(
        postmark_client, 
        imap_client, 
        interval=30,
        reply_handler=process_inbound_reply
    )
    await email_poller.start()
    
    yield
    
    # Shutdown
    if email_poller:
        await email_poller.stop()
    postmark_client = None
    erp_client = None
    imap_client = None
    agent = None
    email_poller = None


app = FastAPI(
    title="Item Data Agent API",
    description="AI agent for supplier communication and item data management",
    version="0.1.0",
    lifespan=lifespan
)


class ItemDataRequest(BaseModel):
    """Request model for initiating supplier communication."""
    
    item_number: str
    item_name: str
    missing_data: list[str]
    supplier_email: EmailStr
    
    class Config:
        json_schema_extra = {
            "example": {
                "item_number": "ITEM-12345",
                "item_name": "Widget Pro 2000",
                "missing_data": ["lead_time", "minimum_order_quantity", "unit_price"],
                "supplier_email": "supplier@example.com"
            }
        }


class AgentResponse(BaseModel):
    """Response model for agent requests."""
    
    status: str
    message: str
    thread_id: str | None = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Item Data Agent API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/v1/request-item-data", response_model=AgentResponse)
async def request_item_data(
    request: ItemDataRequest,
    background_tasks: BackgroundTasks
):
    """Trigger the agent to request missing item data from supplier.
    
    This endpoint initiates the AI agent workflow to:
    1. Compose an email requesting the missing data
    2. Send it to the supplier via Postmark
    3. Receive replies via webhook
    4. Extract information from replies
    5. Update the ERP system when complete
    
    Args:
        request: Item data request with item details and supplier email
        background_tasks: FastAPI background tasks for async processing
        
    Returns:
        Response with status and thread ID for tracking
    """
    if not agent:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized"
        )
    
    try:
        # Create the agent graph
        graph = await agent.create_graph()
        
        # Initial state
        initial_state = {
            "messages": [],
            "item_number": request.item_number,
            "item_name": request.item_name,
            "missing_data": request.missing_data,
            "supplier_email": request.supplier_email,
            "extracted_data": {},
            "email_thread_id": None,
            "conversation_started": False,
            "data_complete": False,
            "erp_updated": False
        }
        
        # Configuration for thread management
        config = {
            "configurable": {
                "thread_id": f"item_{request.item_number}"
            }
        }
        
        # Run the initial workflow (compose and send first email)
        result = await graph.ainvoke(initial_state, config)
        
        # Store thread ID to item number mapping
        if result.get("email_thread_id"):
            thread_id = str(result["email_thread_id"])  # Ensure string
            thread_to_item[thread_id] = request.item_number
            print(f"📎 Mapped thread {thread_id} to item {request.item_number}")
        
        # PoC: Disable background monitoring - no automatic reminders
        # Schedule periodic checks for responses in background
        # background_tasks.add_task(
        #     monitor_conversation,
        #     graph,
        #     config,
        #     request.item_number
        # )
        
        return AgentResponse(
            status="initiated",
            message=f"Started communication with supplier for item {request.item_number}",
            thread_id=result.get("email_thread_id")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


async def monitor_conversation(graph, config: dict, item_number: str):
    """Monitor an ongoing conversation for responses.
    
    This function runs in the background and periodically checks for
    supplier responses, continuing the agent workflow as needed.
    
    Args:
        graph: Compiled LangGraph workflow
        config: Configuration with thread ID
        item_number: Item number being processed
    """
    import asyncio
    
    max_iterations = 10  # Prevent infinite loops
    check_interval = 300  # Check every 5 minutes
    
    for _ in range(max_iterations):
        await asyncio.sleep(check_interval)
        
        try:
            # Get current state
            state_snapshot = await graph.aget_state(config)
            current_state = state_snapshot.values
            
            # If process is complete, stop monitoring
            if current_state.get("erp_updated", False):
                print(f"Item {item_number}: Process completed successfully")
                break
            
            # Continue the workflow to check for new messages
            result = await graph.ainvoke(current_state, config)
            
        except Exception as e:
            print(f"Error monitoring conversation for item {item_number}: {e}")
            break


@app.get("/api/v1/status/{item_number}")
async def get_status(item_number: str):
    """Get the current status of an item data request.
    
    Args:
        item_number: Item number to check status for
        
    Returns:
        Current state of the agent workflow for this item
    """
    if not agent:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized"
        )
    
    try:
        graph = await agent.create_graph()
        config = {
            "configurable": {
                "thread_id": f"item_{item_number}"
            }
        }
        
        # Get current state
        state_snapshot = await graph.aget_state(config)
        
        if not state_snapshot.values:
            raise HTTPException(
                status_code=404,
                detail=f"No active request found for item {item_number}"
            )
        
        current_state = state_snapshot.values
        
        return {
            "item_number": item_number,
            "conversation_started": current_state.get("conversation_started", False),
            "data_complete": current_state.get("data_complete", False),
            "erp_updated": current_state.get("erp_updated", False),
            "extracted_data": current_state.get("extracted_data", {}),
            "email_thread_id": current_state.get("email_thread_id")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving status: {str(e)}"
        )


@app.get("/api/v1/attachments/{item_number}")
async def get_attachments(item_number: str):
    """Get all attachments received for an item data request.
    
    Args:
        item_number: Item number to get attachments for
        
    Returns:
        List of attachment metadata (not the actual files)
    """
    if not postmark_client or not agent:
        raise HTTPException(
            status_code=503,
            detail="Service not initialized"
        )
    
    try:
        # Get the thread ID for this item
        graph = await agent.create_graph()
        config = {
            "configurable": {
                "thread_id": f"item_{item_number}"
            }
        }
        
        state_snapshot = await graph.aget_state(config)
        
        if not state_snapshot.values:
            raise HTTPException(
                status_code=404,
                detail=f"No active request found for item {item_number}"
            )
        
        thread_id = state_snapshot.values.get("email_thread_id")
        
        if not thread_id:
            return {"attachments": []}
        
        # Get attachments from the thread
        attachments = postmark_client.get_thread_attachments(thread_id)
        
        # Return metadata only (not the binary content)
        return {
            "item_number": item_number,
            "thread_id": thread_id,
            "attachments": [
                {
                    "filename": att["filename"],
                    "content_type": att["content_type"],
                    "size": att["size"],
                    "from": att["message_from"],
                    "received_at": att["timestamp"]
                }
                for att in attachments
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving attachments: {str(e)}"
        )


@app.post("/api/v1/webhooks/inbound-email")
async def inbound_email_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook endpoint for receiving inbound emails from Postmark.
    
    Configure this endpoint in your Postmark account:
    https://account.postmarkapp.com/servers/{server-id}/streams/inbound/overview
    
    Set the webhook URL to: https://yourdomain.com/api/v1/webhooks/inbound-email
    
    Args:
        request: FastAPI request containing Postmark webhook payload
        background_tasks: Background tasks for async processing
        
    Returns:
        Success response
    """
    if not postmark_client or not agent:
        raise HTTPException(
            status_code=503,
            detail="Service not initialized"
        )
    
    try:
        # Parse the inbound email webhook payload
        webhook_data = await request.json()
        
        # Process the inbound email
        postmark_client.process_inbound_webhook(webhook_data)
        
        # Trigger the agent to process the new message
        # Extract thread ID and continue the workflow
        headers = webhook_data.get("Headers", [])
        in_reply_to = None
        
        for header in headers:
            if header.get("Name") == "In-Reply-To":
                in_reply_to = header.get("Value")
                break
        
        if in_reply_to:
            # This is a reply to one of our messages - find the item number
            # In production, maintain a mapping of thread_id to item_number in database
            # For now, we'll trigger a check on all active conversations
            background_tasks.add_task(
                process_inbound_reply,
                webhook_data
            )
        
        return {"status": "received", "message": "Email processed successfully"}
        
    except Exception as e:
        print(f"Error processing inbound email webhook: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing webhook: {str(e)}"
        )


async def process_inbound_reply(webhook_data: dict):
    """Process an inbound reply and continue the agent workflow.
    
    Args:
        webhook_data: Webhook payload from Postmark
    """
    if not agent:
        return
    
    print(f"🤖 Processing inbound reply from {webhook_data.get('From')}")
    
    # Extract thread ID from headers
    headers = webhook_data.get("Headers", [])
    in_reply_to = None
    references = None
    
    for header in headers:
        if header.get("Name") == "In-Reply-To":
            in_reply_to = header.get("Value")
        elif header.get("Name") == "References":
            references = header.get("Value")
    
    # Ensure thread_id is a string, not a tuple
    thread_id = in_reply_to or (references.split()[0] if references else None)
    
    # Convert to string if it's a tuple or other type
    if thread_id:
        if isinstance(thread_id, (list, tuple)):
            thread_id = thread_id[0] if thread_id else None
        thread_id = str(thread_id) if thread_id else None
    
    if not thread_id:
        print("   ⚠️  No thread ID found, skipping")
        return
    
    # Look up item number from thread ID
    item_number = thread_to_item.get(thread_id)
    
    if not item_number:
        print(f"   ⚠️  No item number found for thread {thread_id}")
        print(f"   Available mappings: {list(thread_to_item.keys())}")
        return
    
    print(f"   📧 Thread ID: {thread_id}")
    print(f"   📦 Item: {item_number}")
    print(f"   💬 Triggering agent workflow to extract data and respond...")
    
    try:
        graph = await agent.create_graph()
        
        config = {
            "configurable": {
                "thread_id": f"item_{item_number}"
            }
        }
        
        # Get current state
        state_snapshot = await graph.aget_state(config)
        
        if not state_snapshot.values:
            print(f"   ⚠️  No state found for item {item_number}")
            return
        
        current_state = state_snapshot.values
        
        # Continue the workflow - it will check for new messages and respond
        result = await graph.ainvoke(current_state, config)
        
        print(f"   ✓ Agent workflow completed")
        if result.get("data_complete"):
            print(f"   ✓ All data collected!")
        else:
            print(f"   → Clarification email sent")
        
    except Exception as e:
        print(f"   ❌ Error processing reply: {e}")
