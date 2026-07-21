from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class MemoryCreate(BaseModel):
    thread_id: Optional[UUID] = None
    memory_type: str = Field(..., description="episodic, semantic, procedural, entity")
    content: str = Field(..., max_length=1000)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    decay_rate: float = Field(default=0.05)
    is_shared: bool = Field(default=False)
    metadata_json: Optional[str] = "{}"

class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    importance_score: Optional[float] = None
    is_active: Optional[bool] = None
    is_shared: Optional[bool] = None

class MemoryResponse(BaseModel):
    id: UUID
    user_id: UUID
    thread_id: Optional[UUID] = None
    memory_type: str
    content: str
    importance_score: float
    access_count: int
    last_accessed_at: datetime
    created_at: datetime
    decay_rate: float
    is_active: bool
    is_shared: bool
    metadata_json: str

    class Config:
        from_attributes = True

class SearchStrategyEnum(str):
    semantic = "semantic"
    recency = "recency"
    importance = "importance"
    combined = "combined"

class MemorySearchResponse(BaseModel):
    memory: MemoryResponse
    relevance_score: float
    final_score: float

class MemoryStatsResponse(BaseModel):
    total_count: int
    counts_by_type: dict
    avg_importance: float
    active_count: int
    inactive_count: int

class MemoryConflictResponse(BaseModel):
    id: UUID
    user_id: UUID
    memory_id_old: UUID
    memory_id_new: UUID
    old_content: str
    new_content: str
    conflict_type: str
    resolution: Optional[str]
    is_resolved: bool
    created_at: datetime

class ConflictResolveRequest(BaseModel):
    resolution: str
    keep_old: bool

class MemoryEvaluationResponse(BaseModel):
    recall: float
    precision: float
    faithfulness: float
    latency_ms: float
