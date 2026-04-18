"""State management for the LangGraph agent."""
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State schema for the supplier communication agent.
    
    Attributes:
        messages: Conversation history with the supplier
        item_number: Item number being processed
        item_name: Name of the item
        missing_data: List of missing data fields to request
        supplier_email: Email address of the supplier
        extracted_data: Dictionary of extracted information from responses
        email_thread_id: Email thread ID for tracking conversation
        conversation_started: Whether initial email has been sent
        data_complete: Whether all required data has been collected
        erp_updated: Whether ERP has been updated with the data
    """
    
    messages: Annotated[Sequence[BaseMessage], add_messages]
    item_number: str
    item_name: str
    missing_data: list[str]
    supplier_email: str
    extracted_data: dict[str, str]
    email_thread_id: str | None
    conversation_started: bool
    data_complete: bool
    erp_updated: bool
