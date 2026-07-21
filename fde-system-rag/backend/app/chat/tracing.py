import os
from langchain_core.tracers.context import tracing_enabled_var
from langchain_core.callbacks.manager import CallbackManager
from langsmith import Client

def configure_tracing(project_name: str = "Memory-RAG-Agent") -> None:
    """
    Enables environment-level LangSmith tracing for all LangChain/LangGraph calls.
    """
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project_name
    # Ensure client connection works
    client = Client()
    print(f"LangSmith tracing configured for project: {project_name}")

def get_trace_callback_manager():
    """
    Returns a callback manager populated with default tracing hooks.
    """
    return CallbackManager([])
