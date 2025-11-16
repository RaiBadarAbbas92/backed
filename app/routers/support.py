"""API endpoints for the Dragon Funded support bot."""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.models.schemas import (
    IngestionDocument,
    IngestionResult,
    SupportQuery,
    SupportRequest,
    SupportResponse,
)
from app.services.ingestion import IngestionPipeline
from app.services.retrieval import DragonKnowledgeBase
from app.workflows.dragon_funded_graph import DragonFundedOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dragon-funded-support"])


@lru_cache
def get_kb() -> DragonKnowledgeBase:
    """Singleton knowledge base instance."""
    return DragonKnowledgeBase()


@lru_cache
def get_orchestrator() -> DragonFundedOrchestrator:
    """Provide orchestrator instance."""
    return DragonFundedOrchestrator(kb=get_kb())


@router.post("/support/query", response_model=SupportResponse)
def handle_support_query(
    payload: SupportRequest,
    request: Request,
    orchestrator: DragonFundedOrchestrator = Depends(get_orchestrator),
) -> SupportResponse:
    """Process an end-user support query."""
    logger.info("=" * 80)
    logger.info("📥 POST /api/v1/support/query - Request received")
    logger.info("Query: %s", payload.query[:100] + "..." if len(payload.query) > 100 else payload.query)
    logger.info("Client: %s", request.client.host if request.client else "unknown")
    
    try:
        if not payload.query.strip():
            logger.warning("Empty query received")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Message payload cannot be empty."
            )
        
        logger.info("Processing query through orchestrator...")
        support_query = SupportQuery(message=payload.query.strip())
        response = orchestrator.run(support_query)
        
        logger.info("✅ Query processed successfully")
        logger.info("Response length: %d characters", len(response.reply))
        logger.info("Confidence: %.2f", response.confidence)
        logger.info("Sources found: %d", len(response.sources))
        logger.info("Escalation required: %s", response.escalation_required)
        logger.info("=" * 80)
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions (they're intentional)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        error_msg = str(exc)
        logger.exception("❌ ERROR processing query [%s]: %s", error_type, error_msg)
        logger.error("Full traceback:", exc_info=True)
        logger.info("=" * 80)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {error_type} - {error_msg}",
        )


@router.post("/knowledge/ingest", response_model=IngestionResult)
def ingest_knowledge(
    documents: list[IngestionDocument],
) -> IngestionResult:
    """Ingest FAQ or playbook documents into the knowledge base."""
    kb = get_kb()
    pipeline = IngestionPipeline(kb)
    result = pipeline.run(documents)
    if result.indexed == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest documents: {result.detail}",
        )
    return result

