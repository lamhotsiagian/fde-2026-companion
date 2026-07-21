from uuid import UUID
from langchain_core.documents import Document
from loguru import logger
from app.db.pgvector_utils import vector_store
import time

async def vector_search(
    query: str,
    k: int = 10,
    tenant_id: UUID | None = None,
    thread_id: UUID | None = None,
) -> list[Document]:
    """Perform vector similarity search using pgvector."""
    start = time.perf_counter()
    
    filter_dict = {}
    if tenant_id:
        filter_dict["tenant_id"] = str(tenant_id)
    if thread_id:
        filter_dict["thread_id"] = str(thread_id)
    
    documents = await vector_store.asimilarity_search_with_relevance_scores(
        query, k=k, filter=filter_dict if filter_dict else None
    )
    
    result = []
    for doc, score in documents:
        doc.metadata["vector_score"] = score
        result.append(doc)
    
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"Vector search returned {len(result)} results in {elapsed_ms:.1f}ms")
    return result
