# Item Data Agent

An AI-powered agent system that automatically communicates with suppliers via email (using Postmark) to request missing product information, tracks the conversation, extracts data from responses, and updates your ERP system.

## Features

- 🤖 **AI-Powered Communication**: Uses GPT-4 to compose professional emails to suppliers
- 📧 **Postmark Integration**: Sends and receives emails through Postmark's reliable API
- 💬 **Conversation Tracking**: Maintains context across multiple email exchanges
- 🔍 **Information Extraction**: Automatically extracts structured data from supplier responses
- 🔄 **ERP Integration**: Updates your ERP system via REST API when data is complete
- 🚀 **API Triggered**: Simple REST API to initiate supplier communications
- 📊 **State Management**: Uses LangGraph for robust workflow orchestration
- 🪝 **Webhook-Based**: Receives inbound emails via Postmark webhooks (no polling required)

## Architecture

The system uses LangGraph to orchestrate a multi-step workflow:

1. **Compose Email**: AI generates professional request based on missing data
2. **Send Email**: Email sent via Postmark API
3. **Receive Replies**: Inbound emails received via Postmark webhook
4. **Extract Data**: AI extracts structured information from responses
5. **Update ERP**: Pushes extracted data to ERP system via REST API

## Prerequisites

- Python 3.11 or higher
- [UV package manager](https://github.com/astral-sh/uv)
- Postmark account (free tier available at [postmarkapp.com](https://postmarkapp.com))
- OpenAI API key
- ERP system with REST API access

## Installation

### 1. Clone the repository

```bash
cd c:\Dev\ItemDataAgent
```

### 2. Install UV (if not already installed)

```bash
# On Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Set up Postmark

1. Sign up for a free account at [postmarkapp.com](https://postmarkapp.com)
2. Create a new server in your account
3. Get your **Server API Token** from the server settings
4. Set up a sender signature (verify your email domain or individual email)
5. Configure inbound email processing:
   - Go to your server's "Inbound" stream settings
   - Add an inbound domain or use Postmark's inbound forwarding address
   - Set the webhook URL to: `https://yourdomain.com/api/v1/webhooks/inbound-email`
   - Note: During development, use a tool like [ngrok](https://ngrok.com) to expose your local server

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your configuration:

```env
# OpenAI API Configuration
OPENAI_API_KEY=sk-your-api-key-here

# Postmark Configuration
POSTMARK_API_TOKEN=your-postmark-server-token-here
POSTMARK_FROM_EMAIL=sender@yourdomain.com

# ERP API Configuration
ERP_API_BASE_URL=https://your-erp-system.com/api
ERP_API_KEY=your-erp-api-key-here

# Application Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Database (SQLite for conversation tracking)
DATABASE_PATH=./agent_data.db
```

### 6. Run the application

```bash
uv run python -m item_data_agent.main
```

The API server will start at `http://localhost:8000`

## Usage

### API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

### Triggering a Supplier Request

Send a POST request to initiate the agent:

```bash
curl -X POST "http://localhost:8000/api/v1/request-item-data" \
  -H "Content-Type: application/json" \
  -d '{
    "item_number": "ITEM-12345",
    "item_name": "Widget Pro 2000",
    "missing_data": ["lead_time", "minimum_order_quantity", "unit_price"],
    "supplier_email": "supplier@example.com"
  }'
```

Response:
```json
{
  "status": "initiated",
  "message": "Started communication with supplier for item ITEM-12345",
  "thread_id": "18f2c3d4e5a6b7c8"
}
```

### Checking Status

```bash
curl "http://localhost:8000/api/v1/status/ITEM-12345"
```

Response:
```json
{
  "item_number": "ITEM-12345",
  "conversation_started": true,
  "data_complete": true,
  "erp_updated": true,
  "extracted_data": {
    "lead_time": "2-3 weeks",
    "minimum_order_quantity": "100 units",
    "unit_price": "$25.99"
  },
  "email_thread_id": "18f2c3d4e5a6b7c8"
}
```

### Setting Up Webhook for Development

For local development, use ngrok to expose your local server:

```bash
# Install ngrok, then run:
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Configure it in Postmark: https://abc123.ngrok.io/api/v1/webhooks/inbound-email
```

## Project Structure

```
item-data-agent/
├── item_data_agent/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # Application entry point
│   ├── api.py               # FastAPI endpoints (including webhook)
│   ├── agent.py             # LangGraph agent implementation
│   ├── state.py             # Agent state schema
│   ├── config.py            # Configuration management
│   ├── postmark_client.py   # Postmark email integration
│   └── erp_client.py        # ERP API integration
├── tests/                   # Test suite
├── pyproject.toml           # Project dependencies (UV)
├── .env.example             # Environment variables template
├── .gitignore              # Git ignore patterns
└── README.md               # This file
```

## Workflow Details

### 1. Initial Request
When you trigger the API, the agent:
- Receives item details and missing data fields
- Composes a professional email requesting the information
- Sends the email via Postmark
- Returns a thread ID for tracking

### 2. Receiving Responses
When a supplier replies:
- Postmark sends the reply to your webhook endpoint
- The agent processes the inbound email
- Maintains conversation context across multiple exchanges

### 3. Data Extraction
When a response arrives:
- AI analyzes the email content
- Extracts structured data matching the requested fields
- Validates and stores the information

### 4. ERP Update
Once all required data is collected:
- Updates the ERP system via REST API
- Sends confirmation email to supplier
- Marks the process as complete

## Configuration

### Missing Data Fields

You can request any fields your ERP system supports, for example:
- `lead_time`
- `minimum_order_quantity`
- `unit_price`
- `product_dimensions`
- `weight`
- `certifications`
- `warranty_period`

### ERP API Integration

The system expects your ERP API to support:
- `PATCH /items/{item_number}` - Update item fields
- `GET /items/{item_number}` - Retrieve item (optional)

Modify `erp_client.py` to match your ERP's API structure.

### Postmark API Integration

The system expects:
- A valid Postmark Server API Token
- A verified sender email address
- Inbound webhook configured to point to your application

Modify `postmark_client.py` if you need custom email templates or additional features.

## Development

### Running Tests

```bash
uv run pytest
```

### Code Formatting

```bash
uv run ruff check .
uv run ruff format .
```

## Security Considerations

⚠️ **Important Security Notes:**

- Never commit `.env` to version control
- Store API keys securely using environment variables
- Use HTTPS for your webhook endpoint in production
- Implement authentication/authorization for your API endpoints
- Validate webhook requests from Postmark (check signatures)
- Review and limit API scopes to minimum required
- Consider rate limiting for the webhook endpoint

## Troubleshooting

### Email Not Sending

If emails aren't being sent:
1. Verify your Postmark API token is correct
2. Check that your sender email is verified in Postmark
3. Review Postmark activity logs for error messages
4. Ensure you haven't exceeded Postmark's sending limits

### Webhook Not Receiving Emails

If inbound emails aren't being received:
1. Verify webhook URL is correctly configured in Postmark
2. Check that your endpoint is publicly accessible
3. Use ngrok or similar for local development
4. Review Postmark inbound activity logs
5. Ensure your inbound email address/domain is configured

### Missing Data Not Extracted

The AI extraction uses GPT-4. If data isn't being extracted:
- Check that supplier responses contain the information
- Review the extraction prompts in `agent.py`
- Consider adding examples or fine-tuning the prompts

### ERP Update Failures

Check:
- ERP API endpoint is correct in `.env`
- API key has proper permissions
- Network connectivity to ERP system
- ERP API response format matches expectations

## Limitations

- Currently supports text-based email responses only (no attachments)
- Requires public webhook endpoint for receiving emails (use ngrok for dev)
- Email thread tracking relies on email headers (In-Reply-To, References)
- Maximum 10 check iterations per conversation (configurable)
- Email storage is in-memory (in production, use a database)

## Future Enhancements

- [ ] Support for email attachments (PDFs, specs)
- [ ] Multi-language support
- [ ] Webhook signature verification for security
- [ ] Dashboard for monitoring active conversations
- [ ] Retry logic for failed ERP updates
- [ ] Custom email templates per supplier
- [ ] Database persistence for email threads (currently in-memory)
- [ ] Support for multiple email providers

## License

MIT License - see LICENSE file for details

## Support

For issues or questions, please open an issue on GitHub or contact your system administrator.
