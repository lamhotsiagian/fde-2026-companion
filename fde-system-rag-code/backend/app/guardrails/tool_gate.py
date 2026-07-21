"""L5 — Tool gate for slash commands.

The ``/commands`` hit real executors (``app/course/commands.py``) that write
to Postgres: seeding, scale generation up to 10k rows, resets. That is
exactly the destructive-action surface human-in-the-loop approval exists for.

Gate order: allowlist → argument validation → HITL interrupt (destructive) →
per-tenant daily action budget (expensive). Only then does the command reach
its executor — which remains untouched.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text as sql

from .config import guard_settings
from .policy import policy_registry
from .state import GuardedState, GuardVerdict
from .validators import sql_fragment_re

# Central risk classification: the command registry stays the single source
# of truth for *what exists* (app.course.routes.COMMANDS_REGISTRY); the
# policy pack (policies/commands.yaml) owns *how dangerous it is*. The
# legacy module-level names remain importable as live views of the pack.


def __getattr__(name: str):  # PEP 562: legacy constants, now policy-backed
    if name == "DESTRUCTIVE":
        return policy_registry.get().commands.destructive
    if name == "EXPENSIVE":
        return policy_registry.get().commands.expensive
    raise AttributeError(f"module 'app.guardrails.tool_gate' has no attribute '{name}'")


class CatalogScaleArgs(BaseModel):
    """Bounds for /catalog-scale — the command that can write 10k rows."""

    n: int = Field(gt=0, le=10_000)
    seed: int = Field(default=42, ge=0)


class GenericArgs(BaseModel):
    """Fallback: every free-string argument is screened for SQL fragments."""

    model_config = {"extra": "allow"}


ARG_SCHEMAS: dict[str, type[BaseModel]] = {
    "catalog-scale": CatalogScaleArgs,
}


def validate_args(cmd: str, params: dict[str, Any]) -> dict[str, Any]:
    """Validate and coerce arguments; raise ``ValueError`` with a user-safe
    message on violation. SQL-fragment screening applies to every string arg
    regardless of schema, so a future command cannot forget it."""
    for key, val in params.items():
        if isinstance(val, str) and sql_fragment_re().search(val):
            raise ValueError(f"argument '{key}' contains a disallowed token")
    schema = ARG_SCHEMAS.get(cmd, GenericArgs)
    try:
        return schema(**params).model_dump()
    except ValidationError as exc:
        first = exc.errors()[0]
        raise ValueError(f"invalid argument {first['loc']}: {first['msg']}") from exc


async def _daily_command_count(tenant_id: str, cmd: str) -> int:
    """Count today's uses of an expensive command for this tenant (L7-style
    budget applied to actions instead of tokens)."""
    from app.db.main import async_session  # lazy: keep arg-validation import-light
    since = datetime.now(timezone.utc) - timedelta(days=1)
    async with async_session() as session:
        row = await session.execute(
            sql("""
                SELECT count(*) FROM guard_audit
                WHERE tenant_id = :t AND layer = 'tool_gate'
                  AND verdict->>'decision' = 'allow'
                  AND verdict->>'detail' LIKE :cmd
                  AND created_at >= :since
            """),
            {"t": tenant_id, "cmd": f"%{cmd}%", "since": since},
        )
        return int(row.scalar_one() or 0)


async def tool_gate(state: GuardedState) -> Command:
    """Gate a parsed slash command before its executor runs."""
    from app.course.routes import COMMANDS_REGISTRY, parse_slash_command

    t0 = time.perf_counter()
    cmd, params = parse_slash_command(state["sanitized_input"])
    policy = policy_registry.get().commands  # one pack snapshot per request

    def _verdict(decision: str, detail: str) -> list[dict]:
        return [GuardVerdict(
            layer="tool_gate", decision=decision, detail=detail,
            latency_ms=(time.perf_counter() - t0) * 1000,
        ).model_dump()]

    # 1. Closed allowlist — registry + policy risk classes decide what exists.
    ALLOWED_COMMANDS = (COMMANDS_REGISTRY.keys() | policy.destructive
                        | policy.expensive | policy.extra_allowed)
    if cmd not in ALLOWED_COMMANDS:
        return Command(goto="unknown_command_response",
                       update={"guard_verdicts": _verdict("block", f"unknown {cmd}")})

    # 2. Argument validation — bounds, types, SQL-fragment screen.
    try:
        params = validate_args(cmd, params)
    except ValueError as exc:
        return Command(goto="invalid_args_response",
                       update={"guard_verdicts": _verdict("block", f"{cmd}: {exc}")})

    # 3. HITL for destructive ops — LangGraph interrupt; the Postgres
    #    checkpointer parks the run until the UI resumes it with a decision.
    if cmd in policy.destructive:
        decision = interrupt({
            "kind": "confirm_destructive",
            "command": cmd,
            "args": params,
            "warning": "This wipes generated rows for your tenant "
                       "(source-tagged data only; organic activity is kept).",
        })
        if not (isinstance(decision, dict) and decision.get("approved")):
            return Command(goto="cancelled_response",
                           update={"guard_verdicts": _verdict("block", f"{cmd}: user declined")})

    # 4. Per-tenant daily budget for expensive generation commands.
    if cmd in policy.expensive:
        used = await _daily_command_count(state["tenant_id"], cmd)
        if used >= guard_settings.expensive_command_daily_cap:
            return Command(goto="budget_exceeded_response",
                           update={"guard_verdicts": _verdict("block", f"{cmd}: daily cap")})

    return Command(goto="execute_command",
                   update={"guard_verdicts": _verdict("allow", f"{cmd} gated ok")})
