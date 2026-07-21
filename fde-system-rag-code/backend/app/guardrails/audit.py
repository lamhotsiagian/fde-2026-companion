"""L9 — Audit: verdict logging to Postgres.

``guard_audit`` is a projection of the ``guard_verdicts`` accumulated in
graph state — the Postgres checkpointer remains the source of truth for
replay; this table exists for SQL-speed analytics (false-positive rates per
layer per tenant, latency percentiles, per-customer audit exports).

Schema (see scripts/migrations/002_guardrails.sql):
    guard_audit(id, tenant_id, session_id, thread_id, layer,
                verdict jsonb, latency_ms, created_at)
"""

import time

from langgraph.types import Command
from loguru import logger
from sqlalchemy import text as sql

from app.db.main import async_session

from .state import GuardedState, GuardVerdict

END_NODE = "__end__"


async def flush_verdicts(state: GuardedState, thread_id: str | None = None) -> int:
    """Write every verdict from this run to guard_audit. Idempotent per run
    because it is called exactly once, from the terminal audit node."""
    verdicts = state.get("guard_verdicts") or []
    if not verdicts:
        return 0
    async with async_session() as session:
        for v in verdicts:
            await session.execute(
                sql("""
                    INSERT INTO guard_audit
                        (tenant_id, session_id, thread_id, layer, verdict,
                         latency_ms, created_at)
                    VALUES (:tenant, :sess, :thread, :layer,
                            CAST(:verdict AS jsonb), :lat, now())
                """),
                {
                    "tenant": state.get("tenant_id"),
                    "sess": state.get("session_id"),
                    "thread": thread_id,
                    "layer": v.get("layer", "unknown"),
                    "verdict": __import__("json").dumps(v),
                    "lat": v.get("latency_ms", 0.0),
                },
            )
        await session.commit()
    return len(verdicts)


async def audit_write(state: GuardedState) -> Command:
    """Terminal graph node: flush verdicts, never block the user on failure.

    Audit is critical but not availability-critical: if the flush fails we
    log loudly and still return the answer — the checkpointer retains the
    verdicts for later backfill.
    """
    t0 = time.perf_counter()
    try:
        n = await flush_verdicts(state)
        logger.debug("audit_write flushed {} verdicts in {:.1f} ms",
                     n, (time.perf_counter() - t0) * 1000)
    except Exception as exc:
        logger.error("audit_write failed (answer still served): {}", exc)
    return Command(goto=END_NODE)
