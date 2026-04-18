"""Test cases for the Item Data Agent."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from item_data_agent.agent import SupplierAgent
from item_data_agent.state import AgentState


@pytest.fixture
def mock_postmark_client():
    """Create a mock Postmark client."""
    client = MagicMock()
    client.send_email = AsyncMock(return_value="thread_123")
    client.get_thread_messages = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_erp_client():
    """Create a mock ERP client."""
    client = MagicMock()
    client.update_item = AsyncMock(return_value=True)
    client.get_item = AsyncMock(return_value={"item_number": "TEST-001"})
    return client


@pytest.fixture
def supplier_agent(mock_postmark_client, mock_erp_client):
    """Create a supplier agent with mocked dependencies."""
    return SupplierAgent(mock_postmark_client, mock_erp_client)


@pytest.mark.asyncio
async def test_compose_email_initial(supplier_agent):
    """Test composing initial email to supplier."""
    state: AgentState = {
        "messages": [],
        "item_number": "TEST-001",
        "item_name": "Test Widget",
        "missing_data": ["price", "lead_time"],
        "supplier_email": "test@example.com",
        "extracted_data": {},
        "email_thread_id": None,
        "conversation_started": False,
        "data_complete": False,
        "erp_updated": False
    }
    
    result = await supplier_agent.compose_email(state)
    
    assert len(result["messages"]) > 0
    assert "TEST-001" in result["messages"][-1].content


@pytest.mark.asyncio
async def test_send_email(supplier_agent, mock_postmark_client):
    """Test sending email via Postmark."""
    from langchain_core.messages import AIMessage
    
    state: AgentState = {
        "messages": [AIMessage(content="Test email body")],
        "item_number": "TEST-001",
        "item_name": "Test Widget",
        "missing_data": ["price"],
        "supplier_email": "test@example.com",
        "extracted_data": {},
        "email_thread_id": None,
        "conversation_started": False,
        "data_complete": False,
        "erp_updated": False
    }
    
    result = await supplier_agent.send_email(state)
    
    assert result["email_thread_id"] == "thread_123"
    assert result["conversation_started"] is True
    mock_postmark_client.send_email.assert_called_once()


@pytest.mark.asyncio
async def test_should_extract_data_with_new_message(supplier_agent):
    """Test extraction decision with new supplier message."""
    from langchain_core.messages import HumanMessage
    
    state: AgentState = {
        "messages": [HumanMessage(content="The price is $50")],
        "item_number": "TEST-001",
        "item_name": "Test Widget",
        "missing_data": ["price"],
        "supplier_email": "test@example.com",
        "extracted_data": {},
        "email_thread_id": "thread_123",
        "conversation_started": True,
        "data_complete": False,
        "erp_updated": False
    }
    
    decision = supplier_agent.should_extract_data(state)
    
    assert decision == "extract"


@pytest.mark.asyncio
async def test_should_update_erp_when_complete(supplier_agent):
    """Test ERP update decision when data is complete."""
    state: AgentState = {
        "messages": [],
        "item_number": "TEST-001",
        "item_name": "Test Widget",
        "missing_data": ["price"],
        "supplier_email": "test@example.com",
        "extracted_data": {"price": "$50"},
        "email_thread_id": "thread_123",
        "conversation_started": True,
        "data_complete": True,
        "erp_updated": False
    }
    
    decision = supplier_agent.should_update_erp(state)
    
    assert decision == "update"


@pytest.mark.asyncio
async def test_update_erp(supplier_agent, mock_erp_client):
    """Test ERP update functionality."""
    state: AgentState = {
        "messages": [],
        "item_number": "TEST-001",
        "item_name": "Test Widget",
        "missing_data": ["price"],
        "supplier_email": "test@example.com",
        "extracted_data": {"price": "$50"},
        "email_thread_id": "thread_123",
        "conversation_started": True,
        "data_complete": True,
        "erp_updated": False
    }
    
    result = await supplier_agent.update_erp(state)
    
    assert result["erp_updated"] is True
    mock_erp_client.update_item.assert_called_once_with(
        item_number="TEST-001",
        data={"price": "$50"}
    )
