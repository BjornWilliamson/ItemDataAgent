"""Factory for creating configured email backend clients."""
from item_data_agent.config import settings
from item_data_agent.email_client import EmailClient
from item_data_agent.postmark_client import PostmarkClient
from item_data_agent.smtp_client import SMTPClient


def create_email_client() -> EmailClient:
    """Create an email client implementation based on configured backend."""
    backend = settings.email_backend.strip().lower()

    if backend == "postmark":
        return PostmarkClient()

    if backend == "smtp":
        return SMTPClient()

    raise ValueError(
        f"Unsupported EMAIL_BACKEND '{settings.email_backend}'. "
        "Use 'postmark' or 'smtp'."
    )
