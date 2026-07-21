"""L4 — Semantic guard: pgvector-native checks on the draft answer.

Three checks that all reuse the existing embedding stack
(nomic-embed-text + pgvector) — no new inference infrastructure:

1. Topic boundary — the *answer* must live near course-content space, not
   just the question. Catches generation drift the intent guard cannot see.
2. Semantic dedup — per-session answers table with an HNSW index; a
   near-duplicate answer triggers a rephrase instead of a copy-paste loop.
3. Contradiction — llama3.1 as an NLI judge between the screened context
   (premise) and the draft answer (hypothesis). Swap in a DeBERTa-NLI ONNX
   model to take this off the LLM path if judge latency bites.
"""

import time
from typing import Literal

from langchain_ollama import OllamaEmbeddings
from langgraph.types import Command
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import text as sql

from app.config import settings
from app.db.main import async_session

from .config import guard_settings
from .llm_json import as_str, json_complete, make_json_model
from .state import GuardedState, GuardVerdict

NLI_PROMPT = """You are a strict NLI judge. PREMISE is trusted course material;
HYPOTHESIS is a draft answer. Label the pair: entailment (fully supported),
neutral (adds unsupported but non-conflicting content), or contradiction
(conflicts with the premise).

Respond with ONE JSON object and nothing else:
{{"label": "entailment|neutral|contradiction"}}

PREMISE:
{premise}

HYPOTHESIS:
{hypothesis}"""

_NLI_LABELS = {"entailment", "neutral", "contradiction"}


class NLIVerdict(BaseModel):
    label: Literal["entailment", "neutral", "contradiction"]


_embedder = OllamaEmbeddings(
    model=settings.embeddings_model_name, base_url=settings.embeddings_base_url
)
_judge = make_json_model(guard_settings.judge_model)


async def _nli(premise: str, hypothesis: str) -> NLIVerdict:
    """JSON-mode NLI with tolerant label coercion (defaults to neutral)."""
    raw = await json_complete(_judge, NLI_PROMPT.format(
        premise=premise, hypothesis=hypothesis))
    label = as_str(raw.get("label")).lower()
    return NLIVerdict(label=label if label in _NLI_LABELS else "neutral")


async def _pgvector_max_sim(embedding: list[float], table: str,
                            where: str = "", params: dict | None = None) -> float:
    """Max cosine similarity of ``embedding`` against a pgvector table."""
    try:
        async with async_session() as session:
            row = await session.execute(
                sql(f"""
                    SELECT 1 - (embedding <=> CAST(:q AS vector)) AS sim
                    FROM {table} {where}
                    ORDER BY embedding <=> CAST(:q AS vector) LIMIT 1
                """),
                {"q": str(embedding), **(params or {})},
            )
            result = row.scalar_one_or_none()
        return float(result) if result is not None else (1.0 if table == "chapter_centroids" else 0.0)
    except Exception as exc:
        logger.warning(f"_pgvector_max_sim on table {table} skipped ({exc})")
        return 1.0 if table == "chapter_centroids" else 0.0


async def _store_session_answer(state: GuardedState, embedding: list[float]) -> None:
    """Persist the accepted answer's embedding for future dedup checks."""
    try:
        async with async_session() as session:
            await session.execute(
                sql("""
                    INSERT INTO session_answers (tenant_id, session_id, embedding)
                    VALUES (:t, :s, CAST(:e AS vector))
                """),
                {"t": state["tenant_id"], "s": state["session_id"], "e": str(embedding)},
            )
            await session.commit()
    except Exception as exc:
        logger.warning(f"_store_session_answer skipped ({exc})")


def _retry(state: GuardedState, verdict: GuardVerdict, feedback: str) -> Command:
    """Route back to generation with corrective feedback, bounded by
    GUARD_MAX_RETRIES; on exhaustion, degrade to a hedged response."""
    if state.get("retries", 0) >= guard_settings.max_retries:
        return Command(goto="hedged_response",
                       update={"guard_verdicts": [verdict.model_dump()]})
    return Command(goto="generate", update={
        "retries": state.get("retries", 0) + 1,
        "feedback": feedback,
        "guard_verdicts": [verdict.model_dump()],
    })


async def semantic_guard(state: GuardedState) -> Command:
    """Run the three semantic checks; pass forwards to the output guard."""
    t0 = time.perf_counter()
    answer = state["draft_answer"]
    emb = await _embedder.aembed_query(answer)

    # 1. Topic boundary: the answer must sit near course-content space.
    topic_sim = await _pgvector_max_sim(emb, "chapter_centroids")
    if topic_sim < guard_settings.topic_min_cosine:
        verdict = GuardVerdict(layer="semantic", decision="retry",
                               scores={"topic_sim": topic_sim},
                               detail="answer drifted off course scope",
                               latency_ms=(time.perf_counter() - t0) * 1000)
        return _retry(state, verdict,
                      "Answer drifted off recommendation-systems scope. "
                      "Answer strictly from the provided documents.")

    # 2. Semantic dedup within the session (tenant-scoped, like every query).
    dup_sim = await _pgvector_max_sim(
        emb, "session_answers",
        where="WHERE tenant_id = :t AND session_id = :s",
        params={"t": state["tenant_id"], "s": state["session_id"]},
    )
    if dup_sim > guard_settings.dedup_max_cosine:
        verdict = GuardVerdict(layer="semantic", decision="retry",
                               scores={"dup_sim": dup_sim},
                               detail="near-duplicate of a previous answer",
                               latency_ms=(time.perf_counter() - t0) * 1000)
        return _retry(state, verdict,
                      "Rephrase: this repeats an earlier answer in the session. "
                      "Add a new angle or example.")

    # 3. Contradiction against the screened context (NLI judge).
    nli = await _nli(state["screened_context"], answer)
    if nli.label == "contradiction":
        verdict = GuardVerdict(layer="semantic", decision="retry",
                               scores={"topic_sim": topic_sim, "dup_sim": dup_sim},
                               detail="NLI: contradiction vs. course material",
                               latency_ms=(time.perf_counter() - t0) * 1000)
        return _retry(state, verdict,
                      "The answer contradicts the course material. "
                      "Align every claim with the provided documents.")

    await _store_session_answer(state, emb)
    verdict = GuardVerdict(layer="semantic", decision="allow",
                           scores={"topic_sim": topic_sim, "dup_sim": dup_sim},
                           detail=f"nli={nli.label}",
                           latency_ms=(time.perf_counter() - t0) * 1000)
    return Command(goto="output_guard",
                   update={"guard_verdicts": [verdict.model_dump()]})
