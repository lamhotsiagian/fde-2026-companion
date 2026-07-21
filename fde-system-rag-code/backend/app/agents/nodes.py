import json
from loguru import logger
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

try:
    from app.retrieval.hybrid import HybridRetriever
except ImportError:
    class HybridRetriever:
        def __init__(self, tenant_id=None): pass
        async def aretrieve(self, query): return []

try:
    from app.tools.registry import get_tool
except ImportError:
    def get_tool(name): return None

try:
    from app.config import settings
    MODEL_NAME = settings.ollama_model
except ImportError:
    MODEL_NAME = "llama3.2:1b"

from .state import AgentState

llm = ChatOllama(model=MODEL_NAME)

async def planner_node(state: AgentState) -> dict:
    logger.info(f"Step {state.get('step_count', 0)}: planner_node")
    question = state.get("question", "")
    sys_msg = SystemMessage(content="You are a planning assistant. Break down the user's question into a step-by-step resolution plan.")
    human_msg = HumanMessage(content=question)
    response = await llm.ainvoke([sys_msg, human_msg])
    return {"plan": response.content, "step_count": state.get("step_count", 0) + 1}

async def retrieve_node(state: AgentState) -> dict:
    logger.info("retrieve_node")
    try:
        retriever = HybridRetriever(tenant_id=state.get("tenant_id"))
        docs = await retriever.aretrieve(state.get("question", ""))
        formatted_docs = [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in docs]
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        formatted_docs = []
    return {"retrieved_docs": formatted_docs, "step_count": state.get("step_count", 0) + 1}

async def evaluate_node(state: AgentState) -> dict:
    logger.info("evaluate_node")
    plan = state.get("plan", "")
    question = state.get("question", "")
    docs_str = json.dumps(state.get("retrieved_docs", []))
    sys_msg = SystemMessage(content="Evaluate if the retrieved documents are sufficient to answer the question. Reply exactly with one of: 'relevant', 'insufficient', 'need_tool'.")
    human_msg = HumanMessage(content=f"Question: {question}\\nPlan: {plan}\\nDocs: {docs_str}")
    response = await llm.ainvoke([sys_msg, human_msg])
    eval_result = response.content.strip().lower()
    if eval_result not in ["relevant", "insufficient", "need_tool"]:
        eval_result = "relevant"
    return {"evaluation": eval_result, "step_count": state.get("step_count", 0) + 1}

async def tool_node(state: AgentState) -> dict:
    logger.info("tool_node")
    tool_calls = state.get("tool_calls", [])
    results = []
    for tc in tool_calls:
        tool = get_tool(tc.get("name"))
        if tool and hasattr(tool, "arun"):
            res = await tool.arun(tc.get("args"))
            results.append({"tool": tc.get("name"), "result": res})
    return {"tool_calls": results, "step_count": state.get("step_count", 0) + 1}

async def answer_node(state: AgentState) -> dict:
    logger.info("answer_node")
    question = state.get("question", "")
    docs = state.get("retrieved_docs", [])
    plan = state.get("plan", "")
    tools = state.get("tool_calls", [])
    
    sys_msg = SystemMessage(content="You are an expert assistant. Formulate a final comprehensive response using the provided plan, retrieved docs, and tool results.")
    content = f"Question: {question}\\nPlan: {plan}\\nDocs: {json.dumps(docs)}\\nTools: {json.dumps(tools)}"
    human_msg = HumanMessage(content=content)
    
    response = await llm.ainvoke([sys_msg, human_msg])
    return {"answer": response.content, "step_count": state.get("step_count", 0) + 1}

async def reflection_node(state: AgentState) -> dict:
    logger.info("reflection_node")
    answer = state.get("answer", "")
    sys_msg = SystemMessage(content="Self-evaluate the provided answer for quality and faithfulness. Provide a brief reflection.")
    human_msg = HumanMessage(content=f"Answer: {answer}")
    
    response = await llm.ainvoke([sys_msg, human_msg])
    return {"reflection": response.content, "step_count": state.get("step_count", 0) + 1}

async def memory_update_node(state: AgentState) -> dict:
    logger.info("memory_update_node")
    answer = state.get("answer", "")
    sys_msg = SystemMessage(content="Extract key facts or preferences from the answer to update long-term memory. Return each fact on a new line.")
    human_msg = HumanMessage(content=f"Answer: {answer}")
    
    response = await llm.ainvoke([sys_msg, human_msg])
    updates = [line.strip() for line in response.content.split("\\n") if line.strip()]
    return {"memory_updates": updates, "step_count": state.get("step_count", 0) + 1}
