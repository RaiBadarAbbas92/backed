"""LangGraph workflow for the Prop Firm Dragon Funded support bot."""

from __future__ import annotations

import logging
from typing import List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.prompts import assemble_prompt
from app.models.schemas import RetrievedDocument, SupportQuery, SupportResponse
from app.services.domain import DRAGON_CLUB_REWARDS, REFERRAL_PROGRAM
from app.services.llm import GeminiClient, get_gemini_client
from app.services.memory import ConversationMemoryManager
from app.services.retrieval import DragonKnowledgeBase, load_sample_knowledge

logger = logging.getLogger(__name__)


class DragonState(TypedDict, total=False):
    """State carried through the LangGraph workflow."""

    conversation_id: str
    user_message: str
    intent: str
    retrieved_docs: List[RetrievedDocument]
    response_text: str
    confidence: float
    workflow_steps: List[str]
    escalate: bool
    session_summary: str


INTENT_KEYWORDS = {
    "challenge_rules": ["challenge", "phase", "rule", "drawdown", "news", "daily loss"],
    "kyc": ["kyc", "verification", "identity", "passport", "compliance"],
    "withdrawal": ["withdraw", "payout", "bank", "usdt", "payment"],
    "referral": ["referral", "affiliate", "commission", "link"],
    "dragon_club": ["dragon club", "trustpilot", "review", "video", "social"],
}


class DragonFundedOrchestrator:
    """Encapsulates workflow execution."""

    def __init__(
        self,
        kb: Optional[DragonKnowledgeBase] = None,
        llm: Optional[GeminiClient] = None,
        memory_manager: Optional[ConversationMemoryManager] = None,
    ) -> None:
        self._kb = kb or DragonKnowledgeBase()
        self._llm = llm or get_gemini_client()
        self._memory = memory_manager or ConversationMemoryManager()

        # Seed baseline knowledge if empty
        self._bootstrap_knowledge()

        graph = StateGraph(DragonState)
        graph.add_node("classify_intent", self._classify_intent)
        graph.add_node("retrieve_knowledge", self._retrieve_knowledge)
        graph.add_node("compose_response", self._compose_response)
        graph.add_node("evaluate_handoff", self._evaluate_handoff)
        graph.add_node("update_memory", self._update_memory)

        graph.add_edge(START, "classify_intent")
        graph.add_edge("classify_intent", "retrieve_knowledge")
        graph.add_edge("retrieve_knowledge", "compose_response")
        graph.add_edge("compose_response", "evaluate_handoff")
        graph.add_edge("evaluate_handoff", "update_memory")
        graph.add_edge("update_memory", END)

        self._graph = graph.compile()

    def run(self, query: SupportQuery) -> SupportResponse:
        """Execute workflow for a user query."""
        logger.info("Starting workflow execution for conversation: %s", query.conversation_id)
        try:
            self._memory.append(query.conversation_id, "user", query.message)

            initial_state: DragonState = {
                "conversation_id": query.conversation_id,
                "user_message": query.message,
                "workflow_steps": [],
                "session_summary": self._memory.get_session_summary(query.conversation_id),
            }

            logger.info("Invoking workflow graph...")
            final_state = self._graph.invoke(initial_state)
            logger.info("Workflow graph completed. Steps: %s", final_state.get("workflow_steps", []))

            retrieved_docs = final_state.get("retrieved_docs", [])
            logger.info("Retrieved %d documents from knowledge base", len(retrieved_docs))

            response = SupportResponse(
                reply=final_state.get("response_text", ""),
                confidence=final_state.get("confidence", 0.6),
                sources=retrieved_docs,
                workflow_steps=final_state.get("workflow_steps", []),
                escalation_required=final_state.get("escalate", False),
                follow_up_questions=self._derive_follow_ups(final_state.get("intent")),
                suggested_actions=self._derive_suggested_actions(final_state),
            )

            self._memory.append(query.conversation_id, "assistant", response.reply)
            logger.info("Workflow execution completed successfully")
            return response
        except Exception as exc:
            logger.exception("Workflow execution failed: %s", exc)
            raise

    def _classify_intent(self, state: DragonState) -> DragonState:
        """Heuristic intent classifier."""
        message = state["user_message"].lower()
        for intent, keywords in INTENT_KEYWORDS.items():
            if any(keyword in message for keyword in keywords):
                state["intent"] = intent
                break
        else:
            state["intent"] = "general"
        return state

    def _retrieve_knowledge(self, state: DragonState) -> DragonState:
        """Retrieve knowledge snippets."""
        docs = self._kb.retrieve(state["user_message"], k=6)
        state["retrieved_docs"] = docs
        state["confidence"] = max((doc.confidence for doc in docs), default=0.5)
        return state

    def _compose_response(self, state: DragonState) -> DragonState:
        """Invoke Gemini to craft the response."""
        docs = state.get("retrieved_docs", [])
        retrieved_chunks = self._format_retrieval(docs)
        session_summary = state.get("session_summary", "")
        latest_turn = self._memory.get_latest_turn(state["conversation_id"])

        dynamic_overrides = {}
        if state.get("intent") == "dragon_club":
            dynamic_overrides["dragon_club_rewards"] = "\n".join(
                f"{key}: {value}" for key, value in DRAGON_CLUB_REWARDS.items()
            )
        if state.get("intent") == "referral":
            dynamic_overrides["referral_program"] = "\n".join(
                f"{key}: {value}" for key, value in REFERRAL_PROGRAM.items()
            )

        prompt = assemble_prompt(
            retrieved_chunks=retrieved_chunks,
            session_summary=session_summary,
            latest_user_turn=latest_turn or state["user_message"],
            dynamic_overrides=dynamic_overrides or None,
        )

        # Use higher temperature and more tokens for more natural, human-like responses
        response_text = self._llm.generate(
            prompt,
            temperature=0.6,  # Increased for more natural variation
            max_output_tokens=600,  # Increased to allow for natural, flowing responses
        )
        state["response_text"] = response_text
        state["workflow_steps"].append("Composed response via Gemini Pro.")

        # Attempt to extract model-suggested summary
        summary = self._summarize_conversation(state["conversation_id"])
        if summary:
            state["session_summary"] = summary

        return state

    def _evaluate_handoff(self, state: DragonState) -> DragonState:
        """Decide if human escalation is needed."""
        confidence = state.get("confidence", 0.6)
        escalate = confidence < 0.5 or "escalate" in state.get("response_text", "").lower()
        state["escalate"] = escalate
        if escalate:
            state["workflow_steps"].append("Flagged for human escalation.")
        return state

    def _update_memory(self, state: DragonState) -> DragonState:
        """Persist summary back to memory manager."""
        summary = state.get("session_summary")
        if summary:
            self._memory.update_summary(state["conversation_id"], summary)
        return state

    def _summarize_conversation(self, conversation_id: str) -> Optional[str]:
        """Generate a concise summary of the conversation."""
        latest_turns = self._memory.get_recent_transcript(conversation_id)
        prompt = (
            "Summarize the following conversation context in under 60 tokens, "
            "focusing on user objectives and any commitments. Context:\n"
            f"{latest_turns}"
        )
        summary = self._llm.generate(prompt, temperature=0.3, max_output_tokens=120)
        return summary.strip() if summary else None

    def _derive_follow_ups(self, intent: Optional[str]) -> List[str]:
        """Suggest follow-up questions based on intent."""
        mapping = {
            "challenge_rules": [
                "Would you like me to review your latest challenge phase requirements?",
                "Do you need help analyzing your trade log for rule compliance?",
            ],
            "kyc": ["Do you need a link to securely upload your documents?"],
            "withdrawal": ["Should I generate a checklist for your next payout request?"],
            "referral": ["Would you like instructions for sharing your referral dashboard?"],
            "dragon_club": ["Do you want templates for your Trustpilot review or video script?"],
        }
        return mapping.get(intent or "", [])

    def _derive_suggested_actions(self, state: DragonState) -> List[str]:
        """Provide actionable next steps."""
        actions: List[str] = []
        intent = state.get("intent")
        if intent == "challenge_rules":
            actions.append("Review latest account metrics against daily loss and drawdown limits.")
        if intent == "kyc":
            actions.append("Prepare ID and proof of address issued within 90 days for upload.")
        if intent == "withdrawal":
            actions.append("Confirm preferred payout method and eligibility window.")
        if intent == "referral":
            actions.append("Check referral dashboard for pending commissions.")
        if intent == "dragon_club":
            actions.append("Submit proof links for Trustpilot, video, and social posts.")
        if state.get("escalate"):
            actions.append("Open compliance ticket for manual review.")
        return actions

    def _format_retrieval(self, docs: List[RetrievedDocument]) -> str:
        """Render retrieved documents into prompt-friendly format."""
        if not docs:
            return "No matching documents retrieved. Fall back to policy summary."
        formatted = []
        for doc in docs:
            formatted.append(
                f"<doc id='{doc.id}' title='{doc.title}' confidence='{doc.confidence:.2f}'>\n"
                f"{doc.content}\n"
                f"Domains: {', '.join(doc.domain)}\n"
                f"Provenance: {doc.provenance or 'internal knowledge base'}\n"
                "</doc>"
            )
        return "\n".join(formatted)

    def _bootstrap_knowledge(self) -> None:
        """Ensure baseline knowledge is loaded."""
        try:
            seed_documents = load_sample_knowledge()
            if seed_documents:
                self._kb.ingest(seed_documents)
                logger.info("Seed knowledge ingested successfully.")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to ingest seed knowledge: %s", exc)

