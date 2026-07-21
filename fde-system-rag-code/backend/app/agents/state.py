from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    question: str
    plan: str
    retrieved_docs: list[dict]  # list of doc page_content + metadata
    evaluation: str            # 'relevant', 'insufficient', 'need_tool'
    tool_calls: list[dict]
    answer: str
    reflection: str
    memory_updates: list[str]
    tenant_id: str | None
    user_id: str | None
    thread_id: str | None
    step_count: int
