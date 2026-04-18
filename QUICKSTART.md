# Quick Start Scripts

## Prerequisites

1. **Postmark Account**: Sign up at [postmarkapp.com](https://postmarkapp.com)
2. **OpenAI API Key**: Get from [platform.openai.com](https://platform.openai.com)
3. **ERP API Access**: Ensure you have API credentials for your ERP system

## Windows PowerShell

### Initial Setup
```powershell
# Install UV (if not already installed)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies
uv sync

# Run setup script
uv run python setup.py
```

### Run the Application
```powershell
# Start the server
uv run python -m item_data_agent.main
```

### Test the API
```powershell
# Health check
curl http://localhost:8000/health

# Start a supplier request
curl -X POST http://localhost:8000/api/v1/request-item-data `
  -H "Content-Type: application/json" `
  -d "@example_request.json"

# Check status
curl http://localhost:8000/api/v1/status/ITEM-12345
```

## Linux/Mac

### Initial Setup
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Run setup script
uv run python setup.py
```

### Run the Application
```bash
# Start the server
uv run python -m item_data_agent.main
```

### Test the API
```bash
# Health check
curl http://localhost:8000/health

# Start a supplier request
curl -X POST http://localhost:8000/api/v1/request-item-data \
  -H "Content-Type: application/json" \
  -d @example_request.json

# Check status
curl http://localhost:8000/api/v1/status/ITEM-12345
```

## Development Commands

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=item_data_agent

# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Fix linting issues
uv run ruff check --fix .
```

## Environment Variables Required

Before running, ensure your `.env` file has:

```env
OPENAI_API_KEY=sk-...
POSTMARK_API_TOKEN=your-server-token
POSTMARK_FROM_EMAIL=sender@yourdomain.com
ERP_API_BASE_URL=https://...
ERP_API_KEY=...
```

## Postmark Setup

1. Create a server in your Postmark account
2. Get your Server API Token from server settings
3. Verify your sender email address or domain
4. Configure inbound webhook:
   - For local dev: Use ngrok to expose localhost
   - Webhook URL: `https://yourdomain.com/api/v1/webhooks/inbound-email`

## Using ngrok for Development

```bash
# Install ngrok
# Then expose your local server:
ngrok http 8000

# Copy the https URL and configure it as the webhook in Postmark
```
