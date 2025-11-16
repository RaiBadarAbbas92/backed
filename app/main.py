"""FastAPI entrypoint for the Prop Firm Dragon Funded customer support bot."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import support
from app.utils.logger import configure_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title="Prop Firm Dragon Funded Support Bot",
        description=(
            "Customer support assistant for the Dragon Funded forex prop firm, "
            "powered by retrieval-augmented generation and LangGraph workflows."
        ),
        version="0.1.0",
    )

    # Add CORS middleware to allow all origins (including localhost:3000 and 3001)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=False,  # Must be False when using wildcard origins
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    # Add middleware for request logging
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all incoming requests."""
        logger.info("🌐 %s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("📤 Response status: %d", response.status_code)
        return response

    @app.on_event("startup")
    async def validate_config() -> None:
        """Validate configuration on startup."""
        try:
            settings = get_settings()
            if not settings.gemini_api_key or len(settings.gemini_api_key.strip()) == 0:
                logger.error("GEMINI_API_KEY is not set or is empty!")
                logger.error("Please set it as an environment variable or in a .env file")
            else:
                # Mask the API key for logging
                masked_key = settings.gemini_api_key[:8] + "..." if len(settings.gemini_api_key) > 8 else "***"
                logger.info("Gemini API key configured: %s", masked_key)
                logger.info("Using model: %s", settings.gemini_model)
                logger.info("Using embedding model: %s", settings.embedding_model)
        except Exception as exc:
            logger.error("Failed to load configuration: %s", exc)
            logger.error("Make sure GEMINI_API_KEY is set in your environment or .env file")

    app.include_router(support.router, prefix="/api/v1")
    return app


app = create_app()



