"""Main entry point for running the application."""
import uvicorn
from item_data_agent.config import settings


def main():
    """Run the FastAPI application."""
    uvicorn.run(
        "item_data_agent.api:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
