"""Conversation memory management for Dragon Funded bot."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Tuple

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MemoryRecord:
    """Single conversational turn."""

    role: str
    content: str


@dataclass
class SessionMemory:
    """Aggregated memory for a conversation."""

    conversation_id: str
    history: Deque[MemoryRecord] = field(default_factory=lambda: deque(maxlen=12))
    summary: str = ""


class ConversationMemoryManager:
    """Manages short-term and optional episodic memory."""

    def __init__(self) -> None:
        settings = get_settings()
        self._enable_episodic = settings.enable_episodic_memory
        self._sessions: Dict[str, SessionMemory] = {}

    def append(self, conversation_id: str, role: str, content: str) -> None:
        """Add a new message to the conversation."""
        session = self._sessions.setdefault(conversation_id, SessionMemory(conversation_id))
        session.history.append(MemoryRecord(role=role, content=content))

    def get_latest_turn(self, conversation_id: str) -> str:
        """Return the latest user turn for prompting."""
        session = self._sessions.get(conversation_id)
        if not session or not session.history:
            return ""
        latest = [record for record in reversed(session.history) if record.role == "user"]
        return latest[0].content if latest else ""

    def get_session_summary(self, conversation_id: str) -> str:
        """Return or compute a rolling summary."""
        session = self._sessions.get(conversation_id)
        if not session:
            return ""
        if session.summary:
            return session.summary
        return self._summarize_history(session.history)

    def get_recent_transcript(self, conversation_id: str, turns: int = 6) -> str:
        """Return the most recent conversational transcript."""
        session = self._sessions.get(conversation_id)
        if not session or not session.history:
            return ""
        recent = list(session.history)[-turns:]
        return "\n".join(f"{record.role}: {record.content}" for record in recent)

    def update_summary(self, conversation_id: str, summary: str) -> None:
        """Persist a summary from the LangGraph workflow."""
        session = self._sessions.setdefault(conversation_id, SessionMemory(conversation_id))
        session.summary = summary

    @staticmethod
    def _summarize_history(history: Deque[MemoryRecord]) -> str:
        """Fallback summarization heuristic when LLM summary isn't present."""
        turns = list(history)[-4:]
        chunks = [f"{record.role}: {record.content}" for record in turns]
        return " | ".join(chunks)

