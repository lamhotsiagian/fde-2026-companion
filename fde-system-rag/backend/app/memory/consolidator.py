import logging
import json
from uuid import UUID
from typing import Optional
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Memory, MemoryConsolidation, MemoryConflict
from langchain.chat_models import init_chat_model
from app.config import settings

logger = logging.getLogger(__name__)

async def consolidate_memories(session: AsyncSession, user_id: str, thread_id: Optional[UUID], model_name: str) -> dict:
    """
    Chapter 6: Memory Consolidation & Compression
    Combines, summarizes, and updates memories from the current thread or session.
    """
    stmt = select(Memory).where(
        Memory.user_id == user_id,
        Memory.is_active == True,
        Memory.memory_type == "episodic"
    )
    if thread_id:
        stmt = stmt.where(Memory.thread_id == thread_id)
        
    res = await session.execute(stmt)
    memories = res.scalars().all()
    
    if len(memories) < 3:
        return {"status": "skipped", "message": "Not enough memories to consolidate."}
        
    try:
        from app.chat.langgraph_agent import create_model
        model = create_model(model_name=model_name)
        
        mem_text = "\n".join([f"[{m.id}] {m.content}" for m in memories])
        prompt = (
            f"You are a memory consolidation optimizer. Below are episodic memories:\n{mem_text}\n\n"
            f"Consolidate similar memories and produce a list of generalized or condensed semantic/episodic summaries. "
            f"Identify which memories are redundant or can be grouped.\n\n"
            f"Return a JSON object containing:\n"
            f"1. 'consolidated_items': list of new consolidated facts/preferences, each with 'content', 'memory_type' (semantic/episodic), and 'importance_score'.\n"
            f"2. 'redundant_ids': list of memory IDs from the input that are now fully consolidated/replaced.\n"
            f"Do not return explanations. Output ONLY valid JSON."
        )
        
        response = await model.ainvoke(prompt)
        text = response.content.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
            
        result = json.loads(text.strip())
        
        # Deactivate redundant memories
        redundant_ids = [UUID(rid) for rid in result.get("redundant_ids", [])]
        if redundant_ids:
            q = update(Memory).where(Memory.id.in_(redundant_ids)).values(is_active=False)
            await session.execute(q)
            
        # Insert consolidated items
        new_mems = []
        for item in result.get("consolidated_items", []):
            new_mem = Memory(
                user_id=UUID(user_id),
                thread_id=thread_id,
                memory_type=item.get("memory_type", "semantic"),
                content=item.get("content"),
                importance_score=item.get("importance_score", 0.6),
                is_active=True
            )
            session.add(new_mem)
            new_mems.append(new_mem)
            
        # Log consolidation session
        ids_str = ",".join([str(m.id) for m in memories])
        summary_rec = MemoryConsolidation(
            user_id=UUID(user_id),
            level="session",
            summary=f"Consolidated {len(memories)} memories into {len(new_mems)} summary items.",
            source_memory_ids=ids_str
        )
        session.add(summary_rec)
        await session.commit()
        
        return {
            "status": "success",
            "archived_count": len(redundant_ids),
            "new_count": len(new_mems)
        }
    except Exception as e:
        logger.error(f"Memory consolidation failed: {e}")
        return {"status": "error", "message": str(e)}

async def detect_conflicts(session: AsyncSession, user_id: str, model_name: str) -> int:
    """
    Chapter 6 & Chapter 13: Conflict Resolution
    Scans active memories for contradictions and records them in conflict table.
    """
    stmt = select(Memory).where(Memory.user_id == user_id, Memory.is_active == True)
    res = await session.execute(stmt)
    memories = res.scalars().all()
    
    if len(memories) < 2:
        return 0
        
    try:
        from app.chat.langgraph_agent import create_model
        model = create_model(model_name=model_name)
        
        mem_list = [{"id": str(m.id), "content": m.content} for m in memories]
        prompt = (
            f"Analyze the following list of active memories for a user:\n{json.dumps(mem_list)}\n\n"
            f"Find any two memories that directly contradict each other (e.g. 'User hates coffee' vs 'User loves drinking espresso').\n"
            f"If contradictions are found, return a JSON array containing objects with:\n"
            f"- 'old_id': ID of the older contradiction memory\n"
            f"- 'new_id': ID of the newer contradiction memory\n"
            f"- 'conflict_type': Description of the conflict\n"
            f"If no conflicts exist, return an empty array []. Output ONLY JSON."
        )
        response = await model.ainvoke(prompt)
        text = response.content.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
            
        conflicts = json.loads(text.strip())
        added_count = 0
        for conf in conflicts:
            # Check if this conflict was already logged
            old_id = UUID(conf["old_id"])
            new_id = UUID(conf["new_id"])
            check_stmt = select(MemoryConflict).where(
                MemoryConflict.memory_id_old == old_id,
                MemoryConflict.memory_id_new == new_id,
                MemoryConflict.is_resolved == False
            )
            check_res = await session.execute(check_stmt)
            if not check_res.scalar_one_or_none():
                conflict_rec = MemoryConflict(
                    user_id=UUID(user_id),
                    memory_id_old=old_id,
                    memory_id_new=new_id,
                    conflict_type=conf["conflict_type"]
                )
                session.add(conflict_rec)
                added_count += 1
        if added_count > 0:
            await session.commit()
        return added_count
    except Exception as e:
        logger.error(f"Conflict detection failed: {e}")
        return 0
