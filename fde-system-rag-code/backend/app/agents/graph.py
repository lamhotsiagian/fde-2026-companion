from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import (
    planner_node,
    retrieve_node,
    evaluate_node,
    tool_node,
    answer_node,
    reflection_node,
    memory_update_node,
)

def build_enterprise_agent_graph(checkpointer=None):
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("call_tool", tool_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("memory_update", memory_update_node)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Edges
    workflow.add_edge("planner", "retrieve")
    workflow.add_edge("retrieve", "evaluate")
    
    # Conditional routing after evaluate
    def route_after_eval(state: AgentState) -> str:
        eval_res = state.get("evaluation", "relevant")
        if eval_res == "need_tool":
            return "call_tool"
        return "answer"
        
    workflow.add_conditional_edges(
        "evaluate",
        route_after_eval,
        {"call_tool": "call_tool", "answer": "answer"}
    )
    
    workflow.add_edge("call_tool", "answer")
    workflow.add_edge("answer", "reflection")
    workflow.add_edge("reflection", "memory_update")
    workflow.add_edge("memory_update", END)
    
    return workflow.compile(checkpointer=checkpointer)
