"""Configuration management for the Item Data Agent."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # OpenAI Configuration
    openai_api_key: str
    
    # Postmark Configuration
    postmark_api_token: str
    postmark_from_email: str
    
    # IMAP Configuration (for receiving replies)
    imap_server: str = "imap.one.com"
    imap_port: int = 993
    imap_username: str
    imap_password: str
    imap_use_ssl: bool = True
    
    # ERP API Configuration
    erp_api_base_url: str
    erp_api_key: str
    
    # Sender identity (used in outgoing emails)
    sender_name: str = "Procurement"
    sender_title: str = "Procurement Manager"
    company_name: str = "Our Company"

    # Application Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    
    # Database Configuration
    database_path: str = "./agent_data.db"


settings = Settings()
