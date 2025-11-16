"""Pydantic models and shared schema definitions."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from typing import List, Optional

from pydantic import BaseModel, Field


class RetrievedDocument(BaseModel):
    """Structure for retrieved knowledge base documents."""

    id: str
    title: str
    content: str
    domain: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    last_reviewed: Optional[datetime] = None
    provenance: Optional[str] = None


class SupportRequest(BaseModel):
    """Minimal payload accepted from the client."""

    query: str = Field(..., min_length=1, description="End-user message text.")


class SupportQuery(BaseModel):
    """Internal representation of a user turn for workflow processing."""

    message: str
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    channel: str = "web"
    locale: str = "en-US"


class SupportResponse(BaseModel):
    """Customer-facing response."""

    reply: str
    follow_up_questions: List[str] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    sources: List[RetrievedDocument] = Field(default_factory=list)
    escalation_required: bool = False
    workflow_steps: List[str] = Field(default_factory=list)


class IngestionDocument(BaseModel):
    """Input schema for knowledge ingestion."""

    id: str
    title: str
    content: str
    domain: List[str]
    tags: List[str] = Field(default_factory=list)
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    owner: Optional[str] = None
    review_interval_days: int = 90
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    source_url: Optional[str] = None


class IngestionResult(BaseModel):
    """Return payload for ingestion operations."""

    indexed: int
    skipped: int
    detail: Optional[str] = None

