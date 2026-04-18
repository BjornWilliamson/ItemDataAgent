"""Manual test script to check Postmark inbound messages."""
import asyncio
import os
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()

async def test_inbound_polling():
    """Test polling for inbound messages."""
    api_token = os.getenv("POSTMARK_API_TOKEN")
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": api_token
    }
    
    print("Checking for inbound messages in Postmark...\n")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.postmarkapp.com/messages/inbound",
                headers=headers,
                params={"count": 50, "offset": 0},
                timeout=30.0
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response:\n{response.text}\n")
            
            if response.status_code == 200:
                data = response.json()
                messages = data.get("InboundMessages", [])
                print(f"Found {len(messages)} inbound messages:")
                
                for i, msg in enumerate(messages, 1):
                    print(f"\n{i}. Message ID: {msg.get('MessageID')}")
                    print(f"   From: {msg.get('From')}")
                    print(f"   To: {msg.get('To')}")
                    print(f"   Subject: {msg.get('Subject')}")
                    print(f"   Date: {msg.get('ReceivedAt')}")
                    
            else:
                print(f"Error: {response.text}")
                
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_inbound_polling())
