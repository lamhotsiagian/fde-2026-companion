import logging
from datetime import datetime
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Memory, MemoryConsolidation, MemoryConflict, Entity
from app.db.pgvector_utils import delete_document_from_pgvector, search_documents_in_pgvector

logger = logging.getLogger(__name__)

async def forget_user(session: AsyncSession, user_id: str) -> None:
    """
    Chapter 10: Privacy, Security & Governance
    Right to be Forgotten - Cascades delete all memories, entities, conflicts, 
    and consolidations for the given user from PostgreSQL & PGVector.
    """
    # 1. Clear database memory records
    u_id = UUID(user_id)
    await session.execute(delete(MemoryConflict).where(MemoryConflict.user_id == u_id))
    await session.execute(delete(MemoryConsolidation).where(MemoryConsolidation.user_id == u_id))
    await session.execute(delete(Entity).where(Entity.user_id == u_id))
    await session.execute(delete(Memory).where(Memory.user_id == u_id))
    await session.commit()
    
    # 2. Clear pgvector chunks of memory vectors
    try:
        chunks = await search_documents_in_pgvector(filter={"user_id": user_id})
        if chunks:
            chunk_ids = [doc.metadata["id"] for doc in chunks]
            await delete_document_from_pgvector(chunk_ids)
    except Exception as e:
        logger.error(f"Error purging user {user_id} pgvector memory indices: {e}")

async def export_user_data(session: AsyncSession, user_id: str) -> dict:
    """
    Chapter 10: Data Retention and Export (GDPR Portability)
    """
    u_id = UUID(user_id)
    
    mems_stmt = select(Memory).where(Memory.user_id == u_id)
    mems_res = await session.execute(mems_stmt)
    memories = mems_res.scalars().all()
    
    ents_stmt = select(Entity).where(Entity.user_id == u_id)
    ents_res = await session.execute(ents_stmt)
    entities = ents_res.scalars().all()
    
    return {
        "user_id": user_id,
        "exported_at": str(datetime.now()),
        "memories": [
            {
                "type": m.memory_type,
                "content": m.content,
                "created_at": str(m.created_at),
                "importance_score": m.importance_score
            } for m in memories
        ],
        "entities": [
            {
                "name": e.name,
                "type": e.entity_type,
                "attributes": e.attributes_json
            } for e in entities
        ]
    }
