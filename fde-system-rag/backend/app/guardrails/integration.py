"""Integration seam between the guarded graph and the running FastAPI app.

This is the module that makes the guards *actually run*:

* ``resolve_tenant_id`` derives the active tenant from the ``TenantUser`` table
  (the app's real source of tenancy) -- fixing the bug where the graph and the
  rate limiter assumed a ``tenant_id`` that does not exist on the JWT.
* ``build_app_guarded_graph`` compiles the ten-layer graph with the real
  pipeline nodes from ``nodes.py`` injected.
* ``run_guarded_stream`` / ``resume_guarded_stream`` execute the graph and yield
  NDJSON events (``llm_chunk``, ``interrupt``, ``guard_retract``) in the exact
  shape the Next.js chat page already switches on.
"""

from __future__ import annotations

import json
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from loguru import logger
from sqlalchemy import select

from app.db.checkpointer import get_checkpointer
from app.db.main import async_session
from app.db.models import TenantUser

from .config import guard_settings
from .graph import build_guarded_graph
from .nodes import generate_node, nav_helper_node, retriever_node
from .output_guard import StreamGuard

_graph: CompiledStateGraph | None = None


async def resolve_tenant_id(user_id: UUID) -> str | None:
    """Return the user's active tenant id (first membership) or None.

    Mirrors the pattern used throughout ``course/commands.py``:
    ``select(TenantUser).where(TenantUser.user_id == user_id)``.
    """
    async with async_session() as session:
        row = await session.execute(
            select(TenantUser).where(TenantUser.user_id == user_id)
        )
        membership = row.scalars().first()
    return str(membership.tenant_id) if membership else None


async def get_guarded_graph() -> CompiledStateGraph:
    """Build (once) the guarded graph wired to the real pipeline nodes."""
    global _graph
    if _graph is None:
        checkpointer = await get_checkpointer()
        _graph = build_guarded_graph(
            checkpointer=checkpointer,
            retriever_node=retriever_node,
            generate_node=generate_node,
            nav_helper_node=nav_helper_node,
        )
    return _graph


def _final_answer(state: dict) -> str:
    """Pull the last AI message content from a finished graph state."""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, dict):
            role = msg.get("role") or msg.get("type")
            if role in ("ai", "assistant") and msg.get("content"):
                return str(msg["content"])
        else:
            if (isinstance(msg, AIMessage) or (hasattr(msg, "type") and msg.type == "ai")) and getattr(msg, "content", None):
                return str(msg.content)
    return state.get("draft_answer", "")


async def _stream_final(answer: str):
    """Yield the finished answer through StreamGuard (L2 tier A) as NDJSON.

    We generate-then-guard (draft is fully judged by L4/L2 before the user sees
    it), then stream the approved text through the inline PII/profanity scanner
    so the tier-A retraction path is exercised on real output.
    """
    guard = StreamGuard()

    async def _one_chunk():
        yield answer

    async for line in guard.wrap(_one_chunk()):
        yield line


def _interrupt_payload(state: dict) -> dict | None:
    """Detect a LangGraph interrupt (HITL) in an invoke result."""
    intr = state.get("__interrupt__")
    if not intr:
        return None
    first = intr[0]
    value = getattr(first, "value", first)
    return {"type": "interrupt", **(value if isinstance(value, dict) else {"value": value})}


async def get_interrupt_from_snapshot(graph: CompiledStateGraph, config: RunnableConfig) -> dict | None:
    """Query the checkpointer snapshot for any active interrupts."""
    try:
        state_snapshot = await graph.aget_state(config)
        logger.info("get_interrupt_from_snapshot: next={}, tasks={}", state_snapshot.next, state_snapshot.tasks)
        if state_snapshot.tasks:
            for task in state_snapshot.tasks:
                logger.info("task name={}, interrupts={}", task.name, getattr(task, "interrupts", None))
                if task.interrupts:
                    first = task.interrupts[0]
                    val = getattr(first, "value", first)
                    res = {"type": "interrupt"}
                    if isinstance(val, dict):
                        res.update(val)
                    else:
                        res["value"] = val
                    return res
    except Exception as e:
        logger.error("Failed to retrieve interrupt from snapshot: {}", e)
    return None


async def run_guarded_stream(thread_id: UUID, prompt: str, user_id: UUID):
    """Run one turn through the guarded graph; yield NDJSON events."""
    tenant_id = await resolve_tenant_id(user_id)
    graph = await get_guarded_graph()
    config = RunnableConfig(configurable={
        "thread_id": str(thread_id), "user_id": str(user_id),
    })
    state_in = {
        "messages": [HumanMessage(content=prompt)],
        "tenant_id": tenant_id or "",
        "session_id": str(thread_id),
        "user_id": str(user_id),
        "guard_verdicts": [], "retries": 0, "tokens_used": 0,
    }
    try:
        result = await graph.ainvoke(state_in, config=config)
    except Exception as exc:
        logger.error("guarded graph run failed: {}", exc)
        yield json.dumps({"type": "error", "detail": "internal guard error"}) + "\n"
        return

    interrupt = await get_interrupt_from_snapshot(graph, config)
    if not interrupt:
        interrupt = _interrupt_payload(result)
    if interrupt:                      # HITL: surface the confirm request
        yield json.dumps(interrupt) + "\n"
        return

    async for line in _stream_final(_final_answer(result)):
        yield line


async def resume_guarded_stream(thread_id: UUID, approved: bool, user_id: UUID):
    """Resume a parked HITL interrupt with the user's decision; yield NDJSON."""
    graph = await get_guarded_graph()
    config = RunnableConfig(configurable={
        "thread_id": str(thread_id), "user_id": str(user_id),
    })
    try:
        result = await graph.ainvoke(Command(resume={"approved": approved}),
                                     config=config)
    except Exception as exc:
        logger.error("guarded resume failed: {}", exc)
        yield json.dumps({"type": "error", "detail": "resume failed"}) + "\n"
        return
    async for line in _stream_final(_final_answer(result)):
        yield line
