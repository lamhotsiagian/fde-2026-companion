from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langchain_core.documents import Document
from loguru import logger

async def bm25_search(
    query: str,
    session: AsyncSession,
    k: int = 10,
    tenant_id: UUID | None = None,
    thread_id: UUID | None = None,
) -> list[Document]:
    """Perform BM25 search using PostgreSQL full-text search on the langchain_pg_embedding table."""
    # Build SQL query that uses ts_rank + plainto_tsquery against the 'document' column
    # in the langchain_pg_embedding table (which is where PGVector stores documents)
    # Filter by tenant_id and thread_id in the cmetadata JSONB column
    # Return Document objects with page_content and metadata
    
    filters = []
    params = {"query": query, "k": k}
    
    base_sql = """
        SELECT document, cmetadata,
               ts_rank(to_tsvector('english', document), plainto_tsquery('english', :query)) AS rank
        FROM langchain_pg_embedding
        WHERE to_tsvector('english', document) @@ plainto_tsquery('english', :query)
    """
    
    if tenant_id:
        base_sql += " AND cmetadata->>'tenant_id' = :tenant_id"
        params["tenant_id"] = str(tenant_id)
    if thread_id:
        base_sql += " AND cmetadata->>'thread_id' = :thread_id"
        params["thread_id"] = str(thread_id)
    
    base_sql += " ORDER BY rank DESC LIMIT :k"
    
    result = await session.execute(text(base_sql), params)
    rows = result.fetchall()
    
    documents = []
    for row in rows:
        doc = Document(page_content=row[0], metadata=row[1] if row[1] else {})
        doc.metadata["bm25_score"] = float(row[2])
        documents.append(doc)
    
    logger.info(f"BM25 search returned {len(documents)} results for query: {query[:50]}...")
    return documents
