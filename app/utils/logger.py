"""Centralized logging utilities."""

import logging
import os
import sys
from typing import Optional


def configure_logging(level: Optional[str] = None) -> None:
    """Configure application-wide logging."""
    logging_level = level or os.getenv("LOG_LEVEL", "INFO").upper()

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler - always show logs in terminal
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging_level)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging_level)
    root_logger.handlers.clear()  # Remove any existing handlers
    root_logger.addHandler(console_handler)

    # Set specific loggers to appropriate levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)



