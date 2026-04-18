"""LangGraph agent implementation for supplier communication."""
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from item_data_agent.state import AgentState
from item_data_agent.config import settings
from item_data_agent.postmark_client import PostmarkClient
from item_data_agent.erp_client import ERPClient


class SupplierAgent:
    """AI agent for managing supplier communications."""
    
    def __init__(self, postmark_client: PostmarkClient, erp_client: ERPClient):
        """Initialize the supplier agent.
        
        Args:
            postmark_client: Client for Postmark email operations
            erp_client: Client for ERP operations
        """
        self.email_client = postmark_client
        self.erp_client = erp_client
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=settings.openai_api_key
        )
        
    async def create_graph(self):
        """Create the LangGraph workflow."""
        # Create checkpointer for persistence (using in-memory for now)
        memory = MemorySaver()
        
        # Build the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("compose_email", self.compose_email)
        workflow.add_node("send_email", self.send_email)
        workflow.add_node("check_responses", self.check_responses)
        workflow.add_node("extract_data", self.extract_data)
        workflow.add_node("update_erp", self.update_erp)
        
        # Add edges
        workflow.set_entry_point("compose_email")
        workflow.add_edge("compose_email", "send_email")
        workflow.add_edge("send_email", "check_responses")
        workflow.add_conditional_edges(
            "check_responses",
            self.should_extract_data,
            {
                "extract": "extract_data",
                "wait": END,
                "compose": "compose_email"
            }
        )
        workflow.add_conditional_edges(
            "extract_data",
            self.should_update_erp,
            {
                "update": "update_erp",
                "compose": "compose_email"
            }
        )
        workflow.add_edge("update_erp", END)
        
        # Compile the graph with memory
        return workflow.compile(checkpointer=memory)
    
    async def compose_email(self, state: AgentState) -> AgentState:
        """Compose an email to the supplier requesting missing data.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with composed message
        """
        # Determine if this is initial contact or follow-up
        is_followup = state.get("conversation_started", False)
        
        # Check what data still needs to be collected
        missing_fields = [
            field for field in state["missing_data"]
            if field not in state.get("extracted_data", {})
        ]
        
        system_prompt = """You are a professional procurement assistant helping to gather 
        missing product information from suppliers. Be polite, clear, and concise in your 
        communications. Always maintain a professional tone."""
        
        if is_followup:
            user_prompt = f"""Compose a follow-up email to the supplier about item {state['item_number']} 
            ({state['item_name']}). We still need the following information: {', '.join(missing_fields)}.
            
            Reference the previous conversation history and be polite but persistent.
            Keep the email concise and professional."""
        else:
            user_prompt = f"""Compose an initial email to the supplier requesting missing information 
            for item {state['item_number']} ({state['item_name']}).
            
            We need the following information: {', '.join(state['missing_data'])}.
            
            Be polite, introduce the request clearly, and ask for a timely response.
            Keep the email concise and professional."""
        
        messages = [
            SystemMessage(content=system_prompt),
            *state.get("messages", []),
            HumanMessage(content=user_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        return {
            **state,
            "messages": [*state.get("messages", []), response]
        }
    
    async def send_email(self, state: AgentState) -> AgentState:
        """Send the composed email via Postmark.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with email thread ID
        """
        # Get the last AI message (composed email)
        email_body = state["messages"][-1].content
        
        subject = f"Request for Information - Item {state['item_number']}"
        
        # Send email
        thread_id = await self.email_client.send_email(
            to=state["supplier_email"],
            subject=subject,
            body=email_body,
            thread_id=state.get("email_thread_id")
        )
        
        return {
            **state,
            "email_thread_id": thread_id,
            "conversation_started": True
        }
    
    async def check_responses(self, state: AgentState) -> AgentState:
        """Check for new email responses in the thread.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with new messages if any
        """
        if not state.get("email_thread_id"):
            return state
        
        # Get new messages from the email thread
        new_messages = await self.email_client.get_thread_messages(
            thread_id=state["email_thread_id"],
            since_count=len(state.get("messages", []))
        )
        
        # Convert to HumanMessage objects (from supplier)
        human_messages = []
        for msg in new_messages:
            content = msg["body"]
            
            # Add attachment info to the message if present
            if msg.get("attachments"):
                attachment_info = "\n\n[Attachments received:\n"
                for att in msg["attachments"]:
                    att_name = att.get("Name", "unknown")
                    att_type = att.get("ContentType", "unknown")
                    att_size = att.get("ContentLength", 0)
                    attachment_info += f"  - {att_name} ({att_type}, {att_size} bytes)\n"
                attachment_info += "]"
                content += attachment_info
            
            human_messages.append(HumanMessage(content=content))
        
        if human_messages:
            return {
                **state,
                "messages": [*state.get("messages", []), *human_messages]
            }
        
        return state
    
    async def extract_data(self, state: AgentState) -> AgentState:
        """Extract requested information from supplier responses.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with extracted data
        """
        # Get the latest supplier message
        latest_message = state["messages"][-1].content
        
        # Determine what data we're still looking for
        missing_fields = [
            field for field in state["missing_data"]
            if field not in state.get("extracted_data", {})
        ]
        
        extraction_prompt = f"""Analyze the following supplier response and extract any information 
        related to these fields: {', '.join(missing_fields)}.
        
        Supplier response:
        {latest_message}
        
        Return the extracted data in JSON format with field names as keys. 
        Only include fields where you found clear information.
        If no relevant information is found, return an empty object.
        """
        
        messages = [
            SystemMessage(content="You are a data extraction assistant. Extract structured information from text."),
            HumanMessage(content=extraction_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        # Parse the extracted data (simplified - in production, use structured output)
        try:
            import json
            # Extract JSON from response
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            extracted = json.loads(content)
            
            # Merge with existing extracted data
            current_data = state.get("extracted_data", {})
            updated_data = {**current_data, **extracted}
            
            # Check if all data is now complete
            data_complete = all(
                field in updated_data for field in state["missing_data"]
            )
            
            return {
                **state,
                "extracted_data": updated_data,
                "data_complete": data_complete
            }
        except Exception as e:
            print(f"Error extracting data: {e}")
            return state
    
    async def update_erp(self, state: AgentState) -> AgentState:
        """Update the ERP system with extracted data.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with ERP update status
        """
        success = await self.erp_client.update_item(
            item_number=state["item_number"],
            data=state["extracted_data"]
        )
        
        if success:
            # Send confirmation email
            confirmation = f"""Thank you for providing the requested information for item 
            {state['item_number']} ({state['item_name']}). 
            
            We have successfully updated our records with the following data:
            {', '.join(f'{k}: {v}' for k, v in state['extracted_data'].items())}
            
            Best regards"""
            
            await self.email_client.send_email(
                to=state["supplier_email"],
                subject=f"Confirmed - Information Received for Item {state['item_number']}",
                body=confirmation,
                thread_id=state["email_thread_id"]
            )
        
        return {
            **state,
            "erp_updated": success
        }
    
    def should_extract_data(self, state: AgentState) -> Literal["extract", "wait", "compose"]:
        """Determine if we should extract data from the latest message.
        
        Args:
            state: Current agent state
            
        Returns:
            Next node to execute
        """
        messages = state.get("messages", [])
        
        # Check if there's a new message from the supplier
        if not messages or not isinstance(messages[-1], HumanMessage):
            return "wait"
        
        return "extract"
    
    def should_update_erp(self, state: AgentState) -> Literal["update", "compose"]:
        """Determine if all data has been collected and ERP should be updated.
        
        Args:
            state: Current agent state
            
        Returns:
            Next node to execute
        """
        if state.get("data_complete", False):
            return "update"
        
        # If we just received a reply but data is still incomplete,
        # compose a clarification email
        messages = state.get("messages", [])
        if messages and isinstance(messages[-1], HumanMessage):
            return "compose"
        
        # Otherwise end the workflow (don't send unsolicited reminders)
        return "update"
