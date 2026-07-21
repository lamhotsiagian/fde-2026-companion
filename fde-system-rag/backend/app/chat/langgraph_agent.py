from app.config import settings
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from .prompts import SYSTEM_PROMPT
from .tools import tools


def create_model(model_name: str, streaming: bool = False) -> BaseChatModel:
    """Create a retrieval chain based on the provided model name."""
    
    # Handle Ollama provider
    if settings.model_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model_name,
            base_url=settings.model_base_url,
            streaming=streaming
        )

    model = init_chat_model(
        model=model_name,
        model_provider=settings.model_provider,
        api_key=settings.api_key or "mock-key-for-local-ollama",
        base_url=settings.model_base_url or None,
        streaming=streaming,
    )

    return model


def build_retrival_graph(checkpointer: BaseCheckpointSaver, model_name: str) -> CompiledStateGraph:
    """Build a retrieval chain based on the provided model name."""

    model = create_model(model_name=model_name)
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent


def get_enterprise_agent_graph(checkpointer: BaseCheckpointSaver = None):
    """Build the full 7-step enterprise agent graph (Planner -> Retrieve -> Evaluate -> Tool -> Answer -> Reflection -> Memory Update)."""
    from app.agents.graph import build_enterprise_agent_graph
    return build_enterprise_agent_graph(checkpointer=checkpointer)

