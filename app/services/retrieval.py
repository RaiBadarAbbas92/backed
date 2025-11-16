"""Knowledge retrieval and ingestion utilities."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import get_settings
from app.models.schemas import IngestionDocument, RetrievedDocument

logger = logging.getLogger(__name__)


class DragonKnowledgeBase:
    """Vector store-backed knowledge base for Dragon Funded content."""

    def __init__(self) -> None:
        settings = get_settings()
        self._persist_path = Path(settings.vector_store_path)
        self._collection = settings.knowledge_base_collection
        self._persist_path.mkdir(parents=True, exist_ok=True)

        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.gemini_api_key,
        )
        self._vector_store = Chroma(
            collection_name=self._collection,
            embedding_function=self._embeddings,
            persist_directory=str(self._persist_path),
        )

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=75,
            separators=["\n## ", "\n### ", "\n", ".", " "],
        )

    def ingest(self, documents: Iterable[IngestionDocument]) -> None:
        """Ingest structured documents into the vector store."""
        langchain_docs: List[Document] = []

        for doc in documents:
            metadata = {
                "id": doc.id,
                "title": doc.title,
                "domain": doc.domain,
                "tags": doc.tags,
                "confidence": doc.confidence,
                "owner": doc.owner,
                "effective_at": doc.effective_at.isoformat() if doc.effective_at else None,
                "expires_at": doc.expires_at.isoformat() if doc.expires_at else None,
                "source_url": doc.source_url,
            }

            splits = self._splitter.split_text(doc.content)
            for idx, chunk in enumerate(splits):
                chunk_metadata = metadata.copy()
                chunk_metadata.update({"chunk_index": idx, "chunk_count": len(splits)})
                langchain_docs.append(Document(page_content=chunk, metadata=chunk_metadata))

        if not langchain_docs:
            logger.info("No documents to ingest.")
            return

        self._vector_store.add_documents(langchain_docs)
        self._vector_store.persist()
        logger.info("Ingested %s knowledge chunks into collection %s", len(langchain_docs), self._collection)

    def retrieve(self, query: str, k: int = 4) -> List[RetrievedDocument]:
        """Retrieve top-k relevant documents."""
        try:
            results = self._vector_store.similarity_search_with_relevance_scores(query, k=k)
            if not results:
                logger.warning("Vector store returned no results for query. Collection may be empty.")
                return []
        except ValueError as exc:
            error_msg = str(exc)
            logger.error("Similarity search configuration error: %s", error_msg)
            if "API key" in error_msg.lower() or "api_key" in error_msg.lower():
                logger.error("Embedding API key is missing or invalid. Check GEMINI_API_KEY.")
            return []
        except Exception as exc:  # pylint: disable=broad-except
            error_type = type(exc).__name__
            logger.exception("Similarity search failed [%s]: %s", error_type, exc)
            return []

        retrieved: List[RetrievedDocument] = []
        for doc, score in results:
            metadata = doc.metadata or {}
            retrieved.append(
                RetrievedDocument(
                    id=metadata.get("id", ""),
                    title=metadata.get("title", "Dragon Funded Knowledge"),
                    content=doc.page_content,
                    domain=metadata.get("domain", []),
                    confidence=float(metadata.get("confidence", max(0.4, min(1.0, score)))),
                    provenance=metadata.get("source_url"),
                )
            )

        return retrieved


def load_sample_knowledge(base_dir: str = "app/data") -> List[IngestionDocument]:
    """Load sample FAQs and playbooks during bootstrap."""
    sample_path = Path(base_dir) / "seed_knowledge.md"
    if not sample_path.exists():
        logger.warning("Seed knowledge file not found at %s", sample_path)
        return []

    content = sample_path.read_text(encoding="utf-8")
    return [
        IngestionDocument(
            id="dragon-faq-core",
            title="Dragon Funded Core FAQ",
            content=content,
            domain=["dragon_funded", "faq"],
            tags=["kyc", "withdrawal", "referral", "dragon_club"],
            owner="KnowledgeOps",
        )
    ]

