"""Content ingestion pipeline for Dragon Funded knowledge base."""

from __future__ import annotations

import logging
from typing import Iterable

from app.models.schemas import IngestionDocument, IngestionResult
from app.services.retrieval import DragonKnowledgeBase

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Handles preprocessing and indexing operations."""

    def __init__(self, kb: DragonKnowledgeBase) -> None:
        self._kb = kb

    def run(self, documents: Iterable[IngestionDocument]) -> IngestionResult:
        """Execute the ingestion pipeline."""
        docs = list(documents)
        if not docs:
            logger.info("No documents supplied to ingestion pipeline.")
            return IngestionResult(indexed=0, skipped=0, detail="No documents provided.")

        try:
            self._kb.ingest(docs)
            return IngestionResult(indexed=len(docs), skipped=0)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Ingestion failed: %s", exc)
            return IngestionResult(indexed=0, skipped=len(docs), detail=str(exc))








