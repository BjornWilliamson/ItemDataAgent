# Migration from Gmail to Postmark

## Summary of Changes

This document outlines the changes made to migrate the Item Data Agent from Gmail to Postmark for email communications.

## Key Changes

### 1. Email Client Replacement

**Removed:**
- `item_data_agent/gmail_client.py` - Gmail API client with OAuth authentication

**Added:**
- `item_data_agent/postmark_client.py` - Postmark API client with simple token authentication

### 2. Configuration Updates

**`.env.example` and `config.py`:**
- Removed: Gmail API credentials
- Added:
  - `POSTMARK_API_TOKEN` - Server API token from Postmark
  - `POSTMARK_FROM_EMAIL` - Verified sender email address

### 3. Dependencies

**`pyproject.toml`:**
- Removed Google API packages:
  - `google-auth`
  - `google-auth-oauthlib`
  - `google-auth-httplib2`
  - `google-api-python-client`
- No additional packages needed (Postmark uses standard HTTP requests via `httpx`)

### 4. API Webhook Addition

**`api.py`:**
- Added new endpoint: `POST /api/v1/webhooks/inbound-email`
- This webhook receives inbound emails from Postmark
- Background monitoring simplified (webhook-based instead of polling)

### 5. Agent Updates

**`agent.py`:**
- Updated constructor to accept `PostmarkClient` instead of `GmailClient`
- Changed internal reference from `self.gmail_client` to `self.email_client`
- No changes to workflow logic - same LangGraph structure

### 6. Documentation

**Updated files:**
- `README.md` - Complete rewrite with Postmark setup instructions
- `QUICKSTART.md` - Added Postmark configuration steps
- `setup.py` - Updated setup checks for Postmark instead of Gmail

**Removed references to:**
- OAuth authentication flow
- `credentials.json` and `token.json` files
- Gmail API rate limits
- Google Cloud Console setup

### 7. Git Ignore

**`.gitignore`:**
- Removed Gmail-specific files:
  - `credentials.json`
  - `token.json`
  - `token.pickle`

## Benefits of Postmark Over Gmail

1. **Simpler Authentication**: API token instead of OAuth flow
2. **Webhook-Based**: Real-time email reception instead of polling
3. **Designed for Transactional**: Built for programmatic email sending
4. **Better Deliverability**: Professional email infrastructure
5. **No User Interaction Required**: No browser-based OAuth consent
6. **Easier Deployment**: No credential files to manage

## Migration Steps for Existing Deployments

If you have an existing deployment using Gmail:

1. **Sign up for Postmark**:
   - Create account at https://postmarkapp.com
   - Create a server
   - Get Server API Token

2. **Verify Sender Email**:
   - Add and verify your sender email/domain in Postmark

3. **Update Environment Variables**:
   ```env
   POSTMARK_API_TOKEN=your_token_here
   POSTMARK_FROM_EMAIL=sender@yourdomain.com
   ```

4. **Remove Gmail Files** (if they exist):
   ```bash
   Remove-Item credentials.json
   Remove-Item token.json
   ```

5. **Update Dependencies**:
   ```bash
   uv sync
   ```

6. **Configure Inbound Webhook**:
   - Set webhook URL in Postmark settings
   - For dev: Use ngrok to expose localhost
   - For prod: Use your public HTTPS endpoint

7. **Test the Application**:
   ```bash
   uv run python -m item_data_agent.main
   ```

## Architecture Changes

### Before (Gmail):
1. Agent composes email
2. Sends via Gmail API
3. **Polls Gmail API** every 5 minutes for responses
4. Processes responses when found

### After (Postmark):
1. Agent composes email
2. Sends via Postmark API
3. **Webhook receives** inbound emails in real-time
4. Processes responses immediately

## Important Notes

- **Webhook Requirement**: You need a publicly accessible endpoint for production
- **Development**: Use ngrok or similar tool to expose localhost
- **Email Storage**: Currently in-memory (consider database for production)
- **Thread Tracking**: Uses email headers (In-Reply-To, References)

## Support

For Postmark-specific issues:
- Documentation: https://postmarkapp.com/developer
- Support: https://postmarkapp.com/support
- Status: https://status.postmarkapp.com/
