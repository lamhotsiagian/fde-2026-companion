import logging
import math
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Memory
from app.db.pgvector_utils import vector_store
from app.memory.writer import apply_relevance_decay

logger = logging.getLogger(__name__)

async def search_memories(
    session: AsyncSession,
    user_id: str,
    query: str,
    strategy: str = "combined",
    limit: int = 5,
    relevance_threshold: float = 0.4
) -> list[dict]:
    """
    Implements Chapter 5 Retrieval Strategies:
    1. semantic: Semantic similarity search (embeddings)
    2. recency: Recency-weighted retrieval
    3. importance: Importance-weighted retrieval
    4. combined:Stanford Generative Agents formula (recency * importance * relevance)
    """
    # 1. Fetch all active memories for the user
    stmt = select(Memory).where(Memory.user_id == user_id, Memory.is_active == True)
    res = await session.execute(stmt)
    memories = res.scalars().all()
    
    if not memories:
        return []

    # 2. Get semantic similarity scores (relevance)
    # We perform similarity search against vector database or mock matching if vector empty
    scored_memories = []
    
    # Query pgvector for semantic matches
    vector_matches = {}
    try:
        docs = await vector_store.asimilarity_search_with_score(
            query, 
            k=50, 
            filter={"user_id": str(user_id)}
        )
        for doc, score in docs:
            # pgvector cosine similarity mapping or distance conversion
            doc_id = doc.metadata.get("id") or doc.metadata.get("memory_id")
            vector_matches[doc_id] = 1.0 - max(score, 0.0) # Convert distance to similarity
    except Exception as e:
        logger.warning(f"Error querying vector store for memories, falling back: {e}")
        
    for mem in memories:
        # Calculate relevance
        relevance = vector_matches.get(str(mem.id), 0.5)
        # Fallback to basic string overlap if pgvector didn't match
        if str(mem.id) not in vector_matches:
            overlap = set(query.lower().split()) & set(mem.content.lower().split())
            if overlap:
                relevance = min(0.3 + (len(overlap) * 0.1), 1.0)
            else:
                relevance = 0.2
        
        # Calculate recency (retention score using decay function)
        recency = apply_relevance_decay(mem.last_accessed_at, mem.decay_rate)
        
        # Calculate final score based on selected strategy
        if strategy == "semantic":
            final_score = relevance
        elif strategy == "recency":
            final_score = recency
        elif strategy == "importance":
            final_score = mem.importance_score
        else:  # combined
            # Generative Agents: recency * importance * relevance
            # Normalize them to ensure none completely zero out the score
            rec_norm = 0.2 + 0.8 * recency
            imp_norm = 0.2 + 0.8 * mem.importance_score
            rel_norm = 0.2 + 0.8 * relevance
            final_score = rec_norm * imp_norm * rel_norm

        scored_memories.append({
            "memory": mem,
            "relevance_score": relevance,
            "recency_score": recency,
            "importance_score": mem.importance_score,
            "final_score": final_score
        })

    # Sort and filter
    scored_memories.sort(key=lambda x: x["final_score"], reverse=True)
    results = [s for s in scored_memories if s["relevance_score"] >= relevance_threshold]
    
    # Touch accessed memories (async update access count/timestamp)
    for res_item in results[:limit]:
        mem = res_item["memory"]
        mem.access_count += 1
        mem.last_accessed_at = datetime.now()
    await session.commit()
    
    return results[:limit]

async def reformulate_query(query: str, memories: list, model_name: str) -> str:
    """
    Chapter 5: Query reformulation using memory context before retrieval
    """
    if not memories:
        return query
    try:
        from langchain.chat_models import init_chat_model
        from app.config import settings
        
        from app.chat.langgraph_agent import create_model
        model = create_model(model_name=model_name)
        
        mem_str = "\n".join([f"- {m['memory'].content}" for m in memories])
        prompt = (
            f"Given the user's current query: '{query}'\n"
            f"And the following user context/memories:\n{mem_str}\n\n"
            f"Reformulate the query to enrich it with relevant context, optimizing it for RAG retrieval. "
            f"Do not lose the original intent. Return ONLY the reformulated query text."
        )
        response = await model.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.error(f"Failed to reformulate query: {e}")
        return query
