import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Memory
from app.db.pgvector_utils import vector_store

logger = logging.getLogger(__name__)

def inject_memories_to_prompt(prompt: str, memories: list[dict]) -> str:
    """
    Chapter 7: Context Window & Injection Strategy
    Injects memory context into the system or developer instructions conditionally.
    """
    if not memories:
        return prompt
        
    memory_context = "User Context & Background Memories:\n"
    for item in memories:
        mem = item["memory"]
        memory_context += f"- [{mem.memory_type.upper()}] {mem.content}\n"
        
    injected_prompt = (
        f"{prompt}\n\n"
        f"--- MEMORY LAYER CONTEXT ---\n"
        f"{memory_context}"
        f"Use the memory context above to personalize your responses and maintain continuity.\n"
        f"----------------------------"
    )
    return injected_prompt

def manage_token_budget(
    query: str,
    memories: list[dict],
    documents: list,
    budget_limit: int = 2000
) -> tuple[list[dict], list]:
    """
    Chapter 7: Token Budget Management
    Dynamically allocates space for retrieved memories vs. document search.
    Defaults to prioritizing memory slightly but truncating when over budget.
    """
    # Simple character-based estimation (1 token approx 4 characters)
    current_used = len(query) // 4
    allowed_budget = budget_limit - current_used
    
    # Allocate 40% memory, 60% documents
    mem_budget = int(allowed_budget * 0.40)
    doc_budget = allowed_budget - mem_budget
    
    final_memories = []
    mem_used = 0
    for item in memories:
        mem = item["memory"]
        cost = len(mem.content) // 4
        if mem_used + cost <= mem_budget:
            final_memories.append(item)
            mem_used += cost
            
    final_docs = []
    doc_used = 0
    for doc in documents:
        cost = len(doc.page_content) // 4
        if doc_used + cost <= doc_budget:
            final_docs.append(doc)
            doc_used += cost
            
    return final_memories, final_docs
