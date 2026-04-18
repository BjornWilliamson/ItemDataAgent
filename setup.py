"""Setup script for development environment."""
import os
import sys


def setup():
    """Set up the development environment."""
    print("Setting up Item Data Agent development environment...")
    
    # Check if .env exists
    if not os.path.exists('.env'):
        print("\n⚠️  Creating .env file from template...")
        if os.path.exists('.env.example'):
            import shutil
            shutil.copy('.env.example', '.env')
            print("✅ Created .env file. Please edit it with your actual credentials.")
        else:
            print("❌ .env.example not found!")
            sys.exit(1)
    else:
        print("✅ .env file already exists")
    
    # Check for credentials.json
    if not os.path.exists('credentials.json'):
        print("\n⚠️  Postmark Setup Required!")
        print("Please sign up at https://postmarkapp.com/ and:")
        print("1. Create a server")
        print("2. Get your Server API Token")
        print("3. Verify your sender email address")
        print("4. Add credentials to .env file")
    else:
        print("✅ Ready for Postmark integration")
    
    # Create database directory if needed
    os.makedirs('data', exist_ok=True)
    print("✅ Data directory ready")
    
    print("\n" + "="*50)
    print("Setup complete! Next steps:")
    print("="*50)
    print("\n1. Edit .env with your API keys:")
    print("   - OPENAI_API_KEY")
    print("   - POSTMARK_API_TOKEN")
    print("   - POSTMARK_FROM_EMAIL")
    print("   - ERP_API_BASE_URL")
    print("   - ERP_API_KEY")
    print("\n2. Set up Postmark inbound webhook:")
    print("   - Configure webhook URL in Postmark settings")
    print("   - Use ngrok for local development: ngrok http 8000")
    print("\n3. Run the application:")
    print("   uv run python -m item_data_agent.main")
    print("\n4. Visit http://localhost:8000/docs for API documentation")
    print("="*50)


if __name__ == "__main__":
    setup()
