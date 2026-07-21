"""Concrete RAG pipeline nodes the guarded graph wraps.

These are the app-specific nodes injected into ``build_guarded_graph`` (see
``integration.py``). They make the guard contracts real:

* ``retriever_node``  -> populates ``retrieved_docs`` with a per-chunk
  ``cosine_sim`` so L6 relevance gating has a real number to gate on.
* ``generate_node``   -> a real llama3.1 RAG call over the L6-screened context,
  honouring retry feedback and recording REAL token usage into
  ``tokens_used`` (fixes the dead-budget bug).
* ``nav_helper_node`` -> deterministic template answers for navigation intents.

Kept free of any ``app.chat`` import so the guardrails package has no circular
dependency; the checkpointer and models are reached through their own modules.
"""

from __future__ import annotations

import time
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger

from app.config import settings
from app.db.pgvector_utils import vector_store

from .config import guard_settings
from .doc_screen import CONTEXT_CONTRACT
from .state import GuardedState, GuardVerdict

# Reuse the app's model factory (llama3.1 by default) without importing the
# agent graph itself.
from app.chat.langgraph_agent import create_model

RAG_SYSTEM_PROMPT = (
    "You are a teaching assistant for a recommendation-systems course. "
    "Answer only from the reference documents provided. " + CONTEXT_CONTRACT +
    " If the documents do not support an answer, say so plainly rather than "
    "guessing."
)


async def retriever_node(state: GuardedState) -> dict:
    """Real pgvector retrieval with relevance scores.

    Uses ``similarity_search_with_relevance_scores`` so every chunk carries a
    ``cosine_sim`` in ``metadata`` -- exactly the field ``doc_screen`` gates on.
    """
    t0 = time.perf_counter()
    query = state.get("sanitized_input", "")
    try:
        scored = await vector_store.asimilarity_search_with_relevance_scores(
            query, k=5,
        )
    except Exception as exc:  # retrieval outage: hand an empty set to L6
        logger.error("retriever_node failed: {}", exc)
        scored = []

    docs: list[Document] = []
    for doc, score in scored:
        # langchain returns relevance in [0,1]; expose it as cosine_sim for L6.
        md = dict(doc.metadata or {})
        md["cosine_sim"] = float(score)
        docs.append(Document(page_content=doc.page_content, metadata=md))

    verdict = GuardVerdict(
        layer="doc_screen", decision="allow",
        scores={"retrieved": float(len(docs))},
        detail="retrieval complete",
        latency_ms=(time.perf_counter() - t0) * 1000,
    )
    return {"retrieved_docs": docs, "guard_verdicts": [verdict.model_dump()]}


def _extract_tokens(message: Any) -> int:
    """Best-effort real token count from an Ollama/LC response.

    ``ChatOllama`` populates ``usage_metadata`` (input/output/total tokens) and,
    as a fallback, ``response_metadata`` with eval counts. We read whichever is
    present so ``tokens_used`` reflects reality instead of the constant 0 that
    made the budget guard a no-op.
    """
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict) and usage.get("total_tokens"):
        return int(usage["total_tokens"])
    meta = getattr(message, "response_metadata", None) or {}
    prompt_t = int(meta.get("prompt_eval_count", 0) or 0)
    gen_t = int(meta.get("eval_count", 0) or 0)
    if prompt_t or gen_t:
        return prompt_t + gen_t
    # Last-resort estimate so a budget still moves even if metadata is absent.
    text = getattr(message, "content", "") or ""
    return max(1, len(str(text)) // 4)


async def generate_node(state: GuardedState) -> dict:
    """Real RAG generation over screened context, recording token usage.

    Honours ``feedback`` set by a retry from L2/L4 so regeneration is
    corrective rather than identical.
    """
    model = create_model(model_name=settings.model_names[0] if settings.model_names
                         else "llama3.1")
    question = state.get("sanitized_input", "")
    context = state.get("screened_context", "")
    feedback = state.get("feedback", "")

    user_content = f"Reference documents:\n{context}\n\nQuestion: {question}"
    if feedback:
        user_content += f"\n\nReviewer feedback to address: {feedback}"

    messages = [SystemMessage(content=RAG_SYSTEM_PROMPT),
                HumanMessage(content=user_content)]
    response = await model.ainvoke(messages)

    answer = str(response.content)
    turn_tokens = _extract_tokens(response)
    tokens_used = state.get("tokens_used", 0) + turn_tokens

    return {
        "draft_answer": answer,
        "tokens_used": tokens_used,
        "messages": [AIMessage(content=answer)],
    }


# Deterministic navigation answers -- no model call, no hallucination risk.
_NAV_ANSWERS = {
    "cold-start": "Cold-start is Chapter 5. Try `/warm-start-sim` for the "
                  "hands-on transition demo.",
    "evaluation": "Evaluation metrics (RMSE, HR@10, NDCG@10) are Chapter 6. "
                  "Run `/tenant-evaluate` for measured numbers.",
    "matrix": "Matrix factorization is the Chapter 9 capstone. "
              "Run `/capstone-recommend` after `/capstone-train`.",
    "ann": "Approximate nearest neighbors / HNSW is Chapter 8. "
           "Try `/tenant-scoped-ann`.",
}


async def nav_helper_node(state: GuardedState) -> dict:
    """Template navigation answer selected by keyword; falls back to an index."""
    q = state.get("sanitized_input", "").lower()
    for key, ans in _NAV_ANSWERS.items():
        if key in q:
            return {"draft_answer": ans, "messages": [AIMessage(content=ans)]}
    default = ("The course has 10 chapters plus a bonus casebook. Type `/` to "
               "list the hands-on command for each chapter.")
    return {"draft_answer": default, "messages": [AIMessage(content=default)]}
