"""State management for the LangGraph agent."""
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class FieldSpec(TypedDict):
    """Specification for a missing data field."""
    name: str
    type: str  # string | number | boolean | file | date
    description: str | None


class AgentState(TypedDict):
    """State schema for the supplier communication agent."""
    
    messages: Annotated[Sequence[BaseMessage], add_messages]
    item_number: str
    item_name: str
    missing_data: list[FieldSpec]  # List of field specs with name + type
    supplier_email: str
    supplier_company: str | None
    sender_name: str | None
    sender_title: str | None
    company_name: str | None
    extracted_data: dict[str, str]  # field name → extracted value or filename
    email_thread_id: str | None
    conversation_started: bool
    data_complete: bool
    erp_updated: bool
    processed_message_ids: list[str]
