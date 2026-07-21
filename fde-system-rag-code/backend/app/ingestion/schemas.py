from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional

class IngestionRequest(BaseModel):
    chunking_strategy: str = Field(default="recursive")
    chunk_size: int = Field(default=1000)
    chunk_overlap: int = Field(default=200)

class IngestionResponse(BaseModel):
    document_id: UUID
    status: str
    message: str
    job_id: Optional[str] = None

class IngestionStatusResponse(BaseModel):
    document_id: UUID
    status: str
    chunk_count: Optional[int] = None
    processing_time_ms: Optional[float] = None
