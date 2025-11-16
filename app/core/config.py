"""Application configuration utilities."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Environment-driven configuration."""

    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash-lite")
    embedding_model: str = Field(default="models/text-embedding-004")
    vector_store_path: str = Field(default="./storage/vector_store")
    knowledge_base_collection: str = Field(default="dragon_funded_kb")
    allowed_channels: List[str] = Field(default=["web", "mobile", "email", "whatsapp"])
    enable_episodic_memory: bool = Field(default=True)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()

