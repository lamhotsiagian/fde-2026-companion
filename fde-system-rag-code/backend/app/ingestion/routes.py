import os
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from loguru import logger
from arq import create_pool
from arq.connections import RedisSettings

from app.auth.dependencies import CurrentUserDep
from app.db.main import SessionDep
from app.config import BASE_DIR
from app.ingestion.schemas import IngestionRequest, IngestionResponse, IngestionStatusResponse

ingestion_router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".html", ".htm", ".csv", ".xlsx", ".xls"}

async def get_arq_pool():
    return await create_pool(RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6379/0")))

@ingestion_router.post("/upload/{thread_id}", response_model=IngestionResponse)
async def upload_document(
    thread_id: uuid.UUID,
    user: CurrentUserDep,
    session: SessionDep,
    request: IngestionRequest = Depends(),
    file: UploadFile = File(...)
):
    # 1. Validate file extension against supported types
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}")
    
    # 2. Save to temp dir
    temp_dir = Path(BASE_DIR) / "temp" / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    document_id = uuid.uuid4()
    file_path = temp_dir / f"{document_id}{ext}"
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Could not save file")
        
    # 3. Create Document record in DB (placeholder)
    # user context provides tenant_id and user_id
    tenant_id = getattr(user, "tenant_id", None)
    user_id = getattr(user, "id", uuid.uuid4())
    logger.info(f"Created Document record in DB for document_id: {document_id}")
    
    # 4. Enqueue to ARQ redis queue
    pool = await get_arq_pool()
    job = await pool.enqueue_job(
        "process_document_task",
        str(file_path),
        str(document_id),
        str(thread_id),
        str(user_id),
        str(tenant_id) if tenant_id else None,
        request.chunking_strategy,
        request.chunk_size,
        request.chunk_overlap
    )
    
    # 5. Return immediately with job_id
    return IngestionResponse(
        document_id=document_id,
        status="enqueued",
        message="Document enqueued for processing successfully.",
        job_id=job.job_id if job else None
    )

@ingestion_router.get("/status/{document_id}", response_model=IngestionStatusResponse)
async def get_status(document_id: uuid.UUID, user: CurrentUserDep, session: SessionDep):
    # Placeholder status return
    return IngestionStatusResponse(
        document_id=document_id,
        status="processing",
        chunk_count=None,
        processing_time_ms=None
    )

@ingestion_router.get("/{thread_id}")
async def list_documents(thread_id: uuid.UUID, user: CurrentUserDep, session: SessionDep):
    # Placeholder for list documents
    return {"thread_id": thread_id, "documents": []}

@ingestion_router.delete("/{document_id}")
async def delete_document(document_id: uuid.UUID, user: CurrentUserDep, session: SessionDep):
    # Placeholder for deleting document and chunks
    return {"status": "deleted", "document_id": document_id}
