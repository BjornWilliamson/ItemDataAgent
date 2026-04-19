"""LangGraph agent implementation for supplier communication."""
from typing import Literal
import base64
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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
        # Checkpointer will be set externally
        self.checkpointer = None
        
    async def create_graph(self):
        """Create the LangGraph workflow."""
        # Use the checkpointer set during initialization
        
        # Build the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("route_entry", self.route_entry)
        workflow.add_node("compose_email", self.compose_email)
        workflow.add_node("send_email", self.send_email)
        workflow.add_node("check_responses", self.check_responses)
        workflow.add_node("extract_data", self.extract_data)
        workflow.add_node("update_erp", self.update_erp)
        
        # Add edges
        workflow.set_entry_point("route_entry")
        workflow.add_conditional_edges(
            "route_entry",
            self.should_check_or_compose,
            {
                "compose": "compose_email",
                "check": "check_responses"
            }
        )
        workflow.add_edge("compose_email", "send_email")
        workflow.add_edge("send_email", END)
        workflow.add_conditional_edges(
            "check_responses",
            self.should_extract_data,
            {
                "extract": "extract_data",
                "wait": END,
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
        
        # Compile the graph with persistent checkpointer
        return workflow.compile(checkpointer=self.checkpointer)

    async def route_entry(self, state: AgentState) -> AgentState:
        """Pass-through entry node to allow routing decision."""
        return state

    def should_check_or_compose(self, state: AgentState) -> Literal["compose", "check"]:
        """Decide whether to compose a new email or check for replies.
        
        - First run (conversation not started): compose initial email
        - Subsequent runs (triggered by inbound reply): check responses first
        """
        if not state.get("conversation_started"):
            return "compose"
        return "check"

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
        extracted_data = state.get("extracted_data", {})
        missing_fields = [
            field for field in state["missing_data"]
            if field["name"] not in extracted_data
        ]
        received_fields = [
            field for field in state["missing_data"]
            if field["name"] in extracted_data
        ]

        def field_label(f: dict) -> str:
            label = f["description"]  # human-readable label
            if f["type"] == "file":
                label += " [file attachment]"
            elif f["type"] == "number":
                label += " [number]"
            elif f["type"] == "date":
                label += " [date]"
            return label
        
        sender_name = state.get("sender_name") or settings.sender_name
        sender_title = state.get("sender_title") or settings.sender_title
        company_name = state.get("company_name") or settings.company_name
        supplier_company = state.get("supplier_company") or "your company"
        language_map = {
            1: {"name": "Swedish", "subject_request": "Informationsförfrågan", "subject_confirm": "Bekräftelse - Information mottagen"},
            999: {"name": "English", "subject_request": "Request for Information", "subject_confirm": "Confirmed - Information Received"},
        }
        language_code = state.get("language") or 999
        lang = language_map.get(language_code, language_map[999])
        language = lang["name"]

        system_prompt = f"""You are {sender_name}, {sender_title} at {company_name}.
        You are writing professional procurement emails to suppliers to gather missing product data.
        Be polite, clear, and concise. Write the email in {language}. Sign off every email as:
        {sender_name}
        {sender_title}, {company_name}"""

        if is_followup:
            if received_fields and missing_fields:
                user_prompt = f"""Write a follow-up email to {supplier_company} about item {state['item_number']} ({state['item_name']}).

                Thank them for providing: {', '.join(f['description'] for f in received_fields)}.
                We still need the following — do NOT re-request what was already received:
                {chr(10).join(f'  - {field_label(f)}' for f in missing_fields)}

                For file fields, remind them to attach the file to their reply.
                Be polite but clear. Keep it concise."""
            elif missing_fields:
                user_prompt = f"""Write a follow-up email to {supplier_company} about item {state['item_number']} ({state['item_name']}).
                We still need:
                {chr(10).join(f'  - {field_label(f)}' for f in missing_fields)}

                For file fields, ask them to attach the file to their reply.
                Reference the previous conversation. Be polite but persistent. Keep it concise."""
            else:
                user_prompt = f"""Write a brief thank-you email to {supplier_company} confirming receipt of all
                requested information for item {state['item_number']} ({state['item_name']})."""
        else:
            user_prompt = f"""Write an initial email to {supplier_company} requesting missing product information
            for item {state['item_number']} ({state['item_name']}).

            We need the following:
            {chr(10).join(f'  - {field_label(f)}' for f in missing_fields)}

            For file fields, ask them to attach the file to their reply.
            Introduce yourself and the request clearly, and ask for a response at their earliest convenience.
            Keep it concise and professional."""
        
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
        
        # Compose subject line
        language_map = {
            1: {"name": "Swedish", "subject_request": "Informationsförfrågan", "subject_confirm": "Bekräftelse - Information mottagen"},
            999: {"name": "English", "subject_request": "Request for Information", "subject_confirm": "Confirmed - Information Received"},
        }
        lang = language_map.get(state.get("language") or 999, language_map[999])
        base_subject = f"{lang['subject_request']} - {state['item_number']}"
        
        # Get existing thread ID for follow-ups
        existing_thread_id = state.get("email_thread_id")
        
        # If this is a follow-up, add "Re:" prefix for proper threading
        if existing_thread_id:
            subject = f"Re: {base_subject}"
        else:
            subject = base_subject
        
        # Send email
        thread_id = await self.email_client.send_email(
            to=state["supplier_email"],
            subject=subject,
            body=email_body,
            thread_id=existing_thread_id
        )
        
        print(f"📧 Email sent to {state['supplier_email']} (thread: {thread_id})")
        
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
        
        # Use processed message IDs to track what we've already handled
        # This survives app restarts unlike counting messages in state
        processed_ids = set(state.get("processed_message_ids", []))
        
        # Get new messages from the email thread
        new_messages = await self.email_client.get_new_thread_messages(
            thread_id=state["email_thread_id"],
            processed_ids=processed_ids
        )
        
        print(f"📬 Found {len(new_messages)} new message(s) in thread {state['email_thread_id']}")

        # Convert to HumanMessage objects (from supplier)
        human_messages = []
        new_file_attachments = dict(state.get("file_attachments") or {})
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
                    # Store base64 content keyed by filename
                    raw = att.get("Content")
                    if raw is not None:
                        if isinstance(raw, bytes):
                            new_file_attachments[att_name] = base64.b64encode(raw).decode("utf-8")
                        elif isinstance(raw, str):
                            # Already base64 (e.g. from Postmark webhook)
                            new_file_attachments[att_name] = raw
                attachment_info += "]"
                content += attachment_info
            
            human_messages.append({"msg": HumanMessage(content=content), "id": msg["id"]})
        
        if human_messages:
            # Track processed message IDs so we don't re-process after restart
            new_processed_ids = list(processed_ids) + [msg["id"] for msg in new_messages]
            return {
                **state,
                "messages": [*state.get("messages", []), *[m["msg"] for m in human_messages]],
                "processed_message_ids": new_processed_ids,
                "file_attachments": new_file_attachments
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
        import json
        latest_message = state["messages"][-1].content
        
        # Determine what data we're still looking for
        extracted_data = state.get("extracted_data", {})
        missing_fields = [
            field for field in state["missing_data"]
            if field["name"] not in extracted_data
        ]

        # Build a typed field description for the extraction prompt
        field_descriptions = []
        for f in missing_fields:
            desc = f"- {f['name']} ({f['description']}, type: {f['type']})"
            field_descriptions.append(desc)
        
        # Build example with actual field names
        example_fields = {f['name']: ("5.50" if f['type'] == 'number' else ("datasheet.pdf" if f['type'] == 'file' else "value")) for f in missing_fields[:2]}
        
        extraction_prompt = f"""Analyze the following supplier response and extract information 
        for these fields (use the exact field name as the JSON key):
        {chr(10).join(field_descriptions)}
        
        Supplier response:
        {latest_message}
        
        Rules:
        - For 'number' fields: extract only the numeric value (e.g. 5.50, 14)
        - For 'date' fields: extract in ISO format (YYYY-MM-DD) if possible
        - For 'boolean' fields: return true or false
        - For 'string' fields: extract the value as-is
        - For 'file' fields: if an attachment filename is mentioned in [Attachments received:...], 
          use that filename as the value. Otherwise leave it out.
        
        Return ONLY a JSON object using the exact field names as keys.
        Only include fields where information was clearly found.
        If no relevant information is found, return {{}}.
        
        Example: {json.dumps(example_fields)}
        """
        
        messages = [
            SystemMessage(content="You are a data extraction assistant. Extract structured information from text."),
            HumanMessage(content=extraction_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        # Parse the extracted data (simplified - in production, use structured output)
        try:
            # Extract JSON from response
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            extracted = json.loads(content)
            
            # Merge with existing extracted data (no normalization - keys are ERP column names)
            updated_data = {**extracted_data, **extracted}
            
            # Check completeness against required ERP column names
            required_names = {f["name"] for f in state["missing_data"]}
            data_complete = required_names.issubset(updated_data.keys())
            
            print(f"📊 Extracted data: {updated_data} (complete: {data_complete})")
            
            return {
                **state,
                "extracted_data": updated_data,
                "data_complete": data_complete
            }
        except Exception as e:
            print(f"❌ Error extracting data: {e} | LLM response: {response.content}")
            return state
    
    async def update_erp(self, state: AgentState) -> AgentState:
        """Update the ERP system with extracted data.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with ERP update status
        """
        language_map = {
            1: {"name": "Swedish", "subject_request": "Informationsförfrågan", "subject_confirm": "Bekräftelse - Information mottagen"},
            999: {"name": "English", "subject_request": "Request for Information", "subject_confirm": "Confirmed - Information Received"},
        }
        lang = language_map.get(state.get("language") or 999, language_map[999])

        # Build ERP payload - substitute file fields with base64 content
        file_attachments = state.get("file_attachments") or {}
        file_fields = {f["name"] for f in state["missing_data"] if f["type"] == "file"}
        erp_data = {
            key: (file_attachments.get(value, value) if key in file_fields else value)
            for key, value in state["extracted_data"].items()
        }

        success = await self.erp_client.update_item(
            item_number=state["item_number"],
            data=erp_data
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
                subject=f"{lang['subject_confirm']} - {state['item_number']}",
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
        """Determine if all data has been collected and ERP should be updated."""
        if state.get("data_complete", False):
            print("✅ All data collected → updating ERP")
            return "update"
        print("❓ Data incomplete → composing clarification email")
        return "compose"
