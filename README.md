## Customer Support RAG Bot

The Customer Support RAG Bot combines retrieval-augmented generation (RAG), LangGraph workflow orchestration, and layered memory to deliver precise, context-aware answers that stay aligned with policy and playbooks. This document captures the core concepts, architecture, and feature set that power the experience.

### Why It Delivers Better Answers
- Retrieves the latest, domain-tagged FAQs and playbooks, so customers receive policy-compliant guidance every time.
- Uses metadata-aware reranking (freshness, confidence, ownership) to surface the most trustworthy snippets.
- Injects retrieved context into templated prompts, reducing hallucinations and keeping responses auditable.
- Leverages conversation memory, letting the bot understand follow-up questions and maintain continuity across turns.
- Executes operational playbooks through tool nodes, so customers get resolutions instead of explanations when actions are required.

### Knowledge Source Strategy
- **FAQs**: Single-intent answers with “Use When” guidance, dependencies, owner, and review cadence.
- **Playbooks**: SOP-style flows (trigger → prerequisites → steps → contingencies → escalation) stored as structured documents.
- **Dynamic Data**: API-backed facts (pricing, status, inventory) wrapped with schemas and freshness policies.
- **Governance**: Versioning, change logs, and automated regression prompts ensure updates stay consistent.

### Content Ingestion & Chunking
- Normalize text, preserve semantics, and chunk around headings or semantic boundaries (~300–500 tokens with 10–15% overlap).
- Generate per-chunk summaries and keyword lists for hybrid dense + sparse retrieval.
- Attach hierarchical domain tags (`product/payments/refunds`), timestamps, confidence, and provenance IDs at ingest time.

### Memory Architecture
- **Long-Term Memory**: Vector store holding curated knowledge, re-embedded as content evolves.
- **Short-Term Memory**: Rolling conversation buffer with automatic summarization to stay within model context.
- **Working Memory**: Scratchpad within a LangGraph run to track intermediate tool outputs.
- **Episodic Memory (Optional)**: User-specific facts stored with consent, TTLs, and compliance controls.

### Prompt Template Pipeline
- System prompt encodes tone, compliance requirements, and refusal policy.
- Retriever node injects `{use_when}`, `{answer}`, `{provenance}`, `{confidence}` into dedicated slots.
- Memory node supplies `{session_summary}` and `{latest_user_turn}` so the model can reference prior context.
- Templates include negative instructions to prevent misuse (e.g., “If intent is billing, do not execute refunds playbook”).

### LangGraph Workflow
1. **Entry & Intent Classification**: Route the customer turn to FAQ lookup, workflow execution, or human escalation.
2. **Retriever Node**: Hybrid BM25+dense search with metadata filters and reranker.
3. **Tool Nodes**:
   - `faq_lookup` returns curated answers with provenance.
   - `workflow_executor` runs multi-step playbooks, calling external APIs when needed.
   - `handoff_checker` evaluates confidence, compliance flags, and routes to human agents when appropriate.
4. **Response Synthesis**: Prompt template assembles final answer, citing sources and listing actions taken.
5. **Logging & Analytics**: Every turn records inputs, retrieved sources, tool outcomes, and confidence for auditing.

### Key Features
- Policy-aligned answers with explicit provenance and confidence indicators.
- Automatic execution of customer workflows (e.g., status checks, ticket updates) directly from playbooks.
- Hybrid retrieval for both literal keyword matches and semantic similarity.
- Conversational continuity through session summaries and memory layers.
- Governance hooks: owner metadata, review schedules, regression prompts, and analytics dashboards.
- Extensible design—add new knowledge domains or tools without retraining the core model.

### Getting Started
1. Ingest FAQs, playbooks, and API schemas into the vector store using the chunking pipeline.
2. Configure LangGraph nodes (intent classifier, retriever, tool executors, response composer).
3. Define prompt templates with the metadata slots outlined above.
4. Set up evaluation harness (regression prompts, live traffic sampling) before launching to production.
5. Monitor analytics and feedback loops to keep content fresh and continuously improve response quality.

This architecture ensures the bot both understands customer intent and delivers accurate, actionable responses grounded in your organization’s authoritative knowledge.

### Running Locally
1. Install [uv](https://github.com/astral-sh/uv) (`pip install uv` or download the standalone binary).
2. Install a supported Python interpreter (3.10–3.12): `uv python install 3.11`.
3. Sync dependencies and create the isolated environment: `uv sync`.
3. Export credentials: `setx GEMINI_API_KEY "<your_google_api_key>"` (Windows) or `export GEMINI_API_KEY=...` (macOS/Linux).
4. Launch the API: `uv run uvicorn main:app --reload`.
5. Test the `/api/v1/support/query` endpoint with a payload such as:
   ```json
   {
     "conversation_id": "demo-123",
     "user_id": "trader-42",
     "message": "What happens if I break the daily loss limit?"
   }
   ```

### Domain-Specific Coverage
- Forex challenge phases with drawdown, leverage, and news-trading guardrails.
- KYC/AML flows covering documentation requirements, beneficiary matching, and processing SLAs.
- Withdrawal cadence, profit splits, and supported payout channels.
- Referral program economics, dashboards, and payout thresholds.
- Dragon Club reward mechanics with Trustpilot, video, and social proof incentives.

### Managing Dependencies with uv
- Add packages: `uv add <package-name>`
- Add dev-only tools: `uv add --dev <package-name>`
- Run the test suite: `uv run pytest`
- Export a conventional requirements file if needed: `uv pip compile pyproject.toml -o requirements.lock`

