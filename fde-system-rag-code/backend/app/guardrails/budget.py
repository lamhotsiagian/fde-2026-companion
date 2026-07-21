"""L7 — Rate and cost guards.

Even fully local, "cost" is real: GPU/CPU time on the serving box and
Postgres write volume. Two hook points:

* ``rate_limit_middleware`` — FastAPI middleware, per-tenant sliding window
  derived from the existing JWT. Backed by a Postgres ``rate_events`` table
  (no Redis in this stack; swap the backend when you productionize).
* ``budget_guard`` — graph node before generation enforcing per-session and
  per-tenant daily token caps.

Plus ``OllamaCircuitBreaker`` — trips on repeated model failures/timeouts
and routes to the repo's existing deterministic offline-fallback path
(template answers for navigation intents, honest unavailability for theory).
"""

import time
from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from langgraph.types import Command
from loguru import logger
from sqlalchemy import text as sql

from app.db.main import async_session

from .config import guard_settings
from .state import GuardedState, GuardVerdict


async def sliding_window_ok(tenant_id: str, rpm: int) -> bool:
    try:
        now = datetime.now(timezone.utc)
        async with async_session() as session:
            await session.execute(
                sql("INSERT INTO rate_events (tenant_id, created_at) VALUES (:t, :now)"),
                {"t": tenant_id, "now": now},
            )
            row = await session.execute(
                sql("""SELECT count(*) FROM rate_events
                       WHERE tenant_id = :t AND created_at >= :since"""),
                {"t": tenant_id, "since": now - timedelta(seconds=60)},
            )
            await session.commit()
            return int(row.scalar_one()) <= rpm
    except Exception as exc:
        logger.warning(f"sliding_window_ok skipped ({exc})")
        return True


async def _tenant_from_request(request: Request) -> str | None:
    from app.auth.utils import decode_token
    auth = request.headers.get("authorization", "")
    if not auth:
        return None
    token_data = decode_token(auth.removeprefix("Bearer ").strip())
    user_id = getattr(getattr(token_data, "user", None), "id", None)
    if user_id is None:
        return None
    from .integration import resolve_tenant_id
    return await resolve_tenant_id(user_id)


async def rate_limit_middleware(request: Request, call_next):
    if not guard_settings.enabled:
        return await call_next(request)
    if not request.url.path.startswith(("/api/v1/chat", "/api/v1/course")):
        return await call_next(request)

    tenant = await _tenant_from_request(request)
    if tenant and not await sliding_window_ok(tenant, guard_settings.rate_limit_rpm):
        return JSONResponse(
            {"detail": "Rate limit exceeded. Try again in a minute."},
            status_code=429, headers={"Retry-After": "60"},
        )
    return await call_next(request)


async def tenant_daily_tokens(tenant_id: str) -> int:
    try:
        since = datetime.now(timezone.utc) - timedelta(days=1)
        async with async_session() as session:
            row = await session.execute(
                sql("""SELECT coalesce(sum((verdict->>'tokens')::int), 0)
                       FROM guard_audit
                       WHERE tenant_id = :t AND layer = 'budget'
                         AND created_at >= :since"""),
                {"t": tenant_id, "since": since},
            )
            return int(row.scalar_one() or 0)
    except Exception as exc:
        logger.warning(f"tenant_daily_tokens skipped ({exc})")
        return 0


async def budget_guard(state: GuardedState) -> Command:
    """Node before generation: session and tenant token caps."""
    t0 = time.perf_counter()
    session_used = state.get("tokens_used", 0)

    if session_used > guard_settings.session_token_cap:
        verdict = GuardVerdict(layer="budget", decision="block",
                               scores={"session_tokens": float(session_used)},
                               detail="session token cap",
                               latency_ms=(time.perf_counter() - t0) * 1000)
        return Command(goto="budget_exceeded_response",
                       update={"guard_verdicts": [verdict.model_dump()]})

    tenant_used = await tenant_daily_tokens(state["tenant_id"])
    if tenant_used > guard_settings.tenant_daily_token_cap:
        verdict = GuardVerdict(layer="budget", decision="block",
                               scores={"tenant_tokens": float(tenant_used)},
                               detail="tenant daily token cap",
                               latency_ms=(time.perf_counter() - t0) * 1000)
        return Command(goto="budget_exceeded_response",
                       update={"guard_verdicts": [verdict.model_dump()]})

    verdict = GuardVerdict(layer="budget", decision="allow",
                           scores={"session_tokens": float(session_used),
                                   "tenant_tokens": float(tenant_used),
                                   "tokens": float(session_used)},
                           detail="within budget",
                           latency_ms=(time.perf_counter() - t0) * 1000)
    return Command(goto="generate",
                   update={"guard_verdicts": [verdict.model_dump()]})


class OllamaCircuitBreaker:
    """Classic three-state breaker (Nygard, 2018) around Ollama calls.

    closed → open after N consecutive failures/timeouts; open → half-open
    after the reset window; one probe decides. While open, callers route to
    the deterministic offline-fallback path that already ships in the repo.
    """

    def __init__(self,
                 failure_threshold: int = guard_settings.breaker_failure_threshold,
                 reset_seconds: float = guard_settings.breaker_reset_seconds) -> None:
        self._failures = 0
        self._threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if time.monotonic() - self._opened_at >= self._reset_seconds:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        return self.state in ("closed", "half_open")

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold and self._opened_at is None:
            self._opened_at = time.monotonic()
            logger.error("Ollama circuit breaker OPEN after {} failures",
                         self._failures)


ollama_breaker = OllamaCircuitBreaker()
