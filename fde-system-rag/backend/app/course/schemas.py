from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from uuid import UUID

class CourseChatRequest(BaseModel):
    prompt: str
    model_name: str = Field(default="llama3.1")
    thread_id: Optional[UUID] = None

class CommandRequest(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)
    model_name: str = Field(default="llama3.1")

class CommandResponse(BaseModel):
    status: str  # "success" or "needs_seed"
    message: str
    data: Optional[Dict[str, Any]] = None
    suggested_command: Optional[str] = None
    reason: Optional[str] = None

class CourseProgressResponse(BaseModel):
    completed_chapters: List[int]
    total_chapters: int = 9
    details: Dict[str, Any] = Field(default_factory=dict)
