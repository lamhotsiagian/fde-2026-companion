import logging
from uuid import UUID
from typing import Optional
from datetime import datetime
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Memory, Entity, MemoryConflict
from app.db.pgvector_utils import vector_store
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

async def add_memory_item(
    session: AsyncSession,
    user_id: UUID,
    thread_id: Optional[UUID],
    memory_type: str,
    content: str,
    importance_score: float = 0.5,
    is_shared: bool = False,
    metadata_json: str = "{}"
) -> Memory:
    # 1. Deduplicate check: simple similarity search or exact match
    stmt = select(Memory).where(
        Memory.user_id == user_id, 
        Memory.content == content, 
        Memory.is_active == True
    )
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        existing.access_count += 1
        existing.last_accessed_at = datetime.now()
        await session.commit()
        return existing
        
    # 2. Check if we should ignore because importance score is too low
    # (unless it is manually created or forced)
    
    new_mem = Memory(
        user_id=user_id,
        thread_id=thread_id,
        memory_type=memory_type,
        content=content,
        importance_score=importance_score,
        decay_rate=0.05,
        is_active=True,
        is_shared=is_shared,
        metadata_json=metadata_json
    )
    session.add(new_mem)
    await session.commit()
    await session.refresh(new_mem)
    
    # 3. Add to PGVector for semantic indexing
    try:
        from app.db.pgvector_utils import embeddings
        # Create a document chunk for vector store
        doc = Document(
            page_content=content,
            metadata={
                "id": str(new_mem.id),
                "memory_id": str(new_mem.id),
                "user_id": str(user_id),
                "thread_id": str(thread_id) if thread_id else "",
                "type": "memory",
                "memory_type": memory_type
            }
        )
        await vector_store.aadd_documents([doc], ids=[str(new_mem.id)])
    except Exception as e:
        logger.error(f"Error vector indexing memory: {e}")
        
    return new_mem
