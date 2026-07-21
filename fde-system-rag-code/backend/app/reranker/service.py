from langchain_core.documents import Document
from loguru import logger
import time

async def rerank(query: str, documents: list[Document], top_k: int = 5) -> list[Document]:
    """Rerank documents using LLM-based relevance scoring.
    
    Uses the local Ollama LLM to score document relevance to the query.
    Falls back to original ordering if LLM scoring fails.
    """
    if not documents:
        return []
    
    start = time.perf_counter()
    
    try:
        from app.config import settings
        from langchain_ollama import ChatOllama
        
        llm = ChatOllama(
            model=settings.model_names[0],
            base_url=settings.model_base_url,
            temperature=0,
        )
        
        scored_docs = []
        for doc in documents:
            # Ask LLM to rate relevance on 0-10 scale
            prompt = f"""Rate the relevance of this document to the query on a scale of 0-10.
Return ONLY a single number, nothing else.

Query: {query}

Document: {doc.page_content[:500]}

Relevance score (0-10):"""
            
            response = await llm.ainvoke(prompt)
            try:
                score = float(response.content.strip())
                score = max(0.0, min(10.0, score))  # Clamp
            except (ValueError, AttributeError):
                score = 5.0  # Default middle score
            
            doc.metadata["rerank_score"] = score
            scored_docs.append((score, doc))
        
        # Sort by rerank score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        result = [doc for _, doc in scored_docs[:top_k]]
        
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Reranked {len(documents)} docs to top {top_k} in {elapsed_ms:.1f}ms")
        return result
        
    except Exception as e:
        logger.warning(f"Reranker failed, returning original order: {e}")
        return documents[:top_k]
