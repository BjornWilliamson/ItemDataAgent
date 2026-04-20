"""Jeeves ERP API client for updating item information."""
import httpx
from typing import Any

from item_data_agent.config import settings


class ERPClient:
    """Client for interacting with the Jeeves API-Platform."""
    
    def __init__(self):
        """Initialize the API client."""
        self.base_url = settings.erp_api_base_url
        self.api_key = settings.erp_api_key
        self.headers = {
            "X-API-KEY": self.api_key,
            "accept": "application/json",
            "Content-Type": "application/json"
        }
    
    async def update_item(self, item_number: str, data: dict[str, Any], endpoint: str | None = None) -> bool:
        """Update item information in the ERP system.
        
        Args:
            item_number: Item number to update
            data: Dictionary of field names and values to update
            endpoint: Optional static endpoint override; supports absolute URLs or
                relative paths. Item number is sent in the request body only.
            
        Returns:
            True if update was successful, False otherwise
        """
        if endpoint:
            resolved_endpoint = endpoint.strip()
            if resolved_endpoint.startswith(("http://", "https://")):
                url = resolved_endpoint
            else:
                url = f"{self.base_url.rstrip('/')}/{resolved_endpoint.lstrip('/')}"
        else:
            url = f"{self.base_url.rstrip('/')}/itemagent/v1/updateItem"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    url,
                    json=data,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code in (200, 204):
                    print(f"Successfully updated item {item_number} in ERP")
                    return True
                else:
                    print(f"Failed to update ERP. Status: {response.status_code}, Response: {response.text}")
                    return False
                    
        except httpx.RequestError as e:
            print(f"Error updating ERP: {e}")
            return False
