"""Guarded graph state.

Extends the LangGraph agent state with the fields every guard layer reads and
writes. Because the app already runs the Postgres checkpointer
(``app.db.checkpointer``), each ``guard_verdicts`` append is persisted
per-thread automatically — the L9 audit trail rides on existing
infrastructure.
"""

import time
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

GuardLayer = Literal[
    "input", "intent", "doc_screen", "tool_gate", "semantic", "output", "budget"
]
GuardDecision = Literal["allow", "block", "transform", "retry", "escalate", "degrade"]


class GuardVerdict(BaseModel):
    """One guard decision. Verdicts are first-class, typed, auditable data."""

    layer: GuardLayer
    decision: GuardDecision
    scores: dict[str, float] = Field(default_factory=dict)
    detail: str = ""
    latency_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


def _append_verdicts(existing: list[dict], new: list[dict]) -> list[dict]:
    """LangGraph reducer: guard_verdicts is append-only within a run."""
    return (existing or []) + (new or [])


class GuardedState(TypedDict, total=False):
    """Graph state shared by the RAG pipeline and every guard node."""

    # Existing agent fields
    messages: Annotated[list[BaseMessage], add_messages]
    tenant_id: str
    session_id: str
    user_id: str

    # Guard fields (this package)
    sanitized_input: str
    intent: Literal["slash", "recsys_theory", "course_navigation", "off_topic", "abuse"]
    guard_verdicts: Annotated[list[dict], _append_verdicts]
    retries: int
    tokens_used: int
    retrieved_docs: list[Any]
    screened_context: str
    draft_answer: str
    feedback: str


def record(state: GuardedState, verdict: GuardVerdict) -> dict:
    """Build a state update that appends one verdict (reducer-friendly)."""
    return {"guard_verdicts": [verdict.model_dump()]}
