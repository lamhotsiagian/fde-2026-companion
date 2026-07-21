from fastapi import APIRouter
from pydantic import BaseModel
import psutil
import os
from loguru import logger

monitoring_router = APIRouter()

class AdminMetrics(BaseModel):
    users_count: int
    tenants_count: int
    documents_count: int
    queries_count: int
    errors_count: int
    avg_latency_ms: float
    memory_usage_mb: float
    embedding_queue_length: int
    top_questions: list[str]
    hallucination_rate_pct: float

@monitoring_router.get("/dashboard", response_model=AdminMetrics)
async def get_admin_dashboard_metrics():
    logger.info("Fetching admin dashboard metrics")
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)
    
    metrics = AdminMetrics(
        users_count=42,
        tenants_count=5,
        documents_count=128,
        queries_count=1042,
        errors_count=3,
        avg_latency_ms=320.5,
        memory_usage_mb=round(mem_mb, 2),
        embedding_queue_length=0,
        top_questions=[
            "What is our Q3 revenue target?",
            "How do I configure tenant isolation?",
            "Summarize the employee handbook.",
        ],
        hallucination_rate_pct=1.2,
    )
    logger.debug(f"Admin metrics generated, memory usage: {mem_mb:.2f} MB")
    return metrics
