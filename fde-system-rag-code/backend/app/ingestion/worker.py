import arq
from arq.connections import RedisSettings
from pathlib import Path
from uuid import UUID
from loguru import logger
import os

async def process_document_task(
    ctx: dict, 
    file_path: str, 
    document_id: str, 
    thread_id: str, 
    user_id: str, 
    tenant_id: str | None, 
    chunking_strategy: str = "recursive", 
    chunk_size: int = 1000, 
    chunk_overlap: int = 200
) -> dict:
    """ARQ task that processes a document through the ingestion pipeline."""
    from app.ingestion.pipeline import process_document
    result = await process_document(
        file_path=Path(file_path),
        document_id=UUID(document_id),
        thread_id=UUID(thread_id),
        user_id=UUID(user_id),
        tenant_id=UUID(tenant_id) if tenant_id else None,
        chunking_strategy=chunking_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    logger.info(f"Document {document_id} processed: {result}")
    return result

class WorkerSettings:
    functions = [process_document_task]
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    max_jobs = 5
    job_timeout = 600  # 10 minutes
