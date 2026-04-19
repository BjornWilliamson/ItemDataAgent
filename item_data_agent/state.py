"""State management for the LangGraph agent."""
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class FieldSpec(TypedDict):
    """Specification for a missing data field."""
    name: str         # Jeeves column name
    type: str         # Datatype string | number | boolean | file | date
    description: str  # Label used in emails and extraction prompts


class AgentState(TypedDict):
    """State schema for the supplier communication agent."""
    
    messages: Annotated[Sequence[BaseMessage], add_messages]
    item_number: str
    supplier_item_number: str
    item_name: str
    endpoint: str | None
    company_id: str | None
    missing_data: list[FieldSpec]  # List of field specs with name + type
    supplier_email: str
    supplier_company: str | None
    sender_name: str | None
    sender_title: str | None
    company_name: str | None
    language: int  # Jeeves Sprakkode (1=sv, 999=en, needs to be extended, language map in agent.py)
    extracted_data: dict[str, str]  # field name → extracted value or filename
    file_attachments: dict[str, str]  # filename → base64 content (for file-type fields)
    email_thread_id: str | None
    conversation_started: bool
    data_complete: bool
    erp_updated: bool
    processed_message_ids: list[str]
