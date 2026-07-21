"""Final wired guarded graph.

Assembles every guard node around the existing slash/RAG pipeline:

    START
     └─ input_guard ── slash ─► tool_gate ─► [interrupt?] ─► execute_command
          │                                        │              │
          │ free text                     denied/invalid    output_guard(schema)
          ▼                                        ▼              ▼
      intent_router ── off_topic ─► deflect      response      audit_write
          │ recsys_theory                          nodes           │
          ▼                                                        ▼
      retriever ─► doc_screen ─► budget_guard ─► generate ─► semantic_guard
                                                     ▲               │ fail
                                                     └── retry ≤ 2 ──┘
                                                    semantic pass ─► output_guard
                                                                     │
                                                            audit_write ─► END

The Postgres checkpointer persists state + verdicts at every super-step;
the FastAPI rate-limit middleware wraps the whole thing.
"""

import json

from langchain_core.messages import AIMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .audit import audit_write
from .budget import budget_guard
from .doc_screen import doc_screen
from .input_guard import input_guard
from .intent_guard import intent_router, route_by_intent
from .output_guard import output_guard
from .semantic_guard import semantic_guard
from .state import GuardedState
from .tool_gate import tool_gate


# --- Terminal response nodes -------------------------------------------------
def _say(text: str):
    """Factory for terminal nodes that emit one fixed AI message."""
    async def node(state: GuardedState) -> dict:
        return {"messages": [AIMessage(content=text)]}
    return node


rejection_handler = _say(
    "I can't help with that request. I'm the course assistant for "
    "recommendation systems — ask me about the course material.")
deflect = _say(
    "That's outside the scope of this course. Try a recommender-systems "
    "question, or type / to see the hands-on commands for each chapter.")
no_context_response = _say(
    "Honest answer: the course material doesn't cover that, so I won't "
    "guess. Chapters 1–10 are searchable — try rephrasing toward "
    "recommender-systems concepts.")
unknown_command_response = _say(
    "Unknown command. Type / to list available course commands.")
invalid_args_response = _say(
    "That command's arguments are invalid or out of bounds. "
    "Example: /catalog-scale n=2000 seed=42 (n must be 1–10000).")
cancelled_response = _say("Cancelled — no data was changed.")
budget_exceeded_response = _say(
    "You've hit the usage budget for today. Budgets reset every 24h; "
    "contact your admin to raise the cap.")
malformed_response = _say(
    "The command produced a malformed result and was withheld. "
    "The incident is logged; please retry.")


async def hedged_response(state: GuardedState) -> dict:
    """Degrade path after retry exhaustion: ship the draft with an explicit
    uncertainty note instead of looping the GPU forever."""
    draft = state.get("draft_answer", "")
    note = ("\n\n> Note: I couldn't fully verify every claim above against "
            "the course material. Treat details as provisional and check the "
            "cited chapters.")
    return {"messages": [AIMessage(content=draft + note)]}


async def execute_command(state: GuardedState) -> dict:
    """Run the (already gated) slash command through the existing registry."""
    from app.course.routes import parse_slash_command, run_command_by_name
    from app.db.main import async_session
    from uuid import UUID

    cmd, params = parse_slash_command(state["sanitized_input"])
    async with async_session() as session:
        res = await run_command_by_name(cmd, params, session,
                                        UUID(state["user_id"]))
    return {"draft_answer": res.model_dump_json(),
            "messages": [AIMessage(content=res.message)]}


def build_guarded_graph(checkpointer: BaseCheckpointSaver,
                        retriever_node, generate_node,
                        nav_helper_node) -> CompiledStateGraph:
    """Wire the ten-layer guarded graph around the app's RAG nodes.

    ``retriever_node`` / ``generate_node`` / ``nav_helper_node`` are the
    existing pipeline stages (pgvector retrieval, llama3.1 generation,
    template navigation answers) — injected so this module has no circular
    import on app.chat.
    """
    g = StateGraph(GuardedState)

    # Guard nodes (this package)
    g.add_node("input_guard", input_guard)
    g.add_node("intent_router", intent_router)
    g.add_node("doc_screen", doc_screen)
    g.add_node("budget_guard", budget_guard)
    g.add_node("tool_gate", tool_gate)
    g.add_node("semantic_guard", semantic_guard)
    g.add_node("output_guard", output_guard)
    g.add_node("audit_write", audit_write)

    # Pipeline nodes (existing app code, injected)
    g.add_node("retriever", retriever_node)
    g.add_node("generate", generate_node)
    g.add_node("nav_helper", nav_helper_node)
    g.add_node("execute_command", execute_command)

    # Terminal response nodes
    for name, node in [
        ("rejection_handler", rejection_handler), ("deflect", deflect),
        ("no_context_response", no_context_response),
        ("unknown_command_response", unknown_command_response),
        ("invalid_args_response", invalid_args_response),
        ("cancelled_response", cancelled_response),
        ("budget_exceeded_response", budget_exceeded_response),
        ("malformed_response", malformed_response),
        ("hedged_response", hedged_response),
    ]:
        g.add_node(name, node)

    # Edges. Nodes that return Command(goto=...) route themselves; the static
    # edges below cover the plain nodes.
    g.add_edge(START, "input_guard")
    g.add_conditional_edges("intent_router", route_by_intent, {
        "retriever": "retriever", "nav_helper": "nav_helper",
        "deflect": "deflect", "rejection_handler": "rejection_handler",
    })
    g.add_edge("retriever", "doc_screen")
    g.add_edge("generate", "semantic_guard")
    g.add_edge("execute_command", "output_guard")
    g.add_edge("nav_helper", "audit_write")
    for terminal in ("rejection_handler", "deflect", "no_context_response",
                     "unknown_command_response", "invalid_args_response",
                     "cancelled_response", "budget_exceeded_response",
                     "malformed_response", "hedged_response"):
        g.add_edge(terminal, "audit_write")

    return g.compile(checkpointer=checkpointer)
