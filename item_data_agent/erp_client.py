"""ERP API client for updating item information."""
import httpx
from typing import Any

from item_data_agent.config import settings


class ERPClient:
    """Client for interacting with the ERP REST API."""
    
    def __init__(self):
        """Initialize the ERP client."""
        self.base_url = settings.erp_api_base_url
        self.api_key = settings.erp_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def update_item(self, item_number: str, data: dict[str, Any]) -> bool:
        """Update item information in the ERP system.
        
        Args:
            item_number: Item number to update
            data: Dictionary of field names and values to update
            
        Returns:
            True if update was successful, False otherwise
        """
        url = f"{self.base_url}/items/{item_number}"
        
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
    
    async def get_item(self, item_number: str) -> dict[str, Any] | None:
        """Get item information from the ERP system.
        
        Args:
            item_number: Item number to retrieve
            
        Returns:
            Item data dictionary or None if not found
        """
        url = f"{self.base_url}/items/{item_number}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Item not found or error. Status: {response.status_code}")
                    return None
                    
        except httpx.RequestError as e:
            print(f"Error retrieving item from ERP: {e}")
            return None
