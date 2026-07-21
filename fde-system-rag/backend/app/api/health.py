from fastapi import APIRouter
from sqlalchemy import text
import redis.asyncio as aioredis
import os

health_router = APIRouter()

@health_router.get("/health")
async def health_check():
    status = {"status": "healthy", "postgres": "unknown", "redis": "unknown"}
    
    # Test Postgres
    try:
        from app.db.main import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["postgres"] = "healthy"
    except Exception as e:
        status["postgres"] = f"unhealthy: {e}"
        status["status"] = "degraded"
        
    # Test Redis
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = aioredis.from_url(redis_url)
        await client.ping()
        await client.close()
        status["redis"] = "healthy"
    except Exception as e:
        status["redis"] = f"unhealthy: {e}"
        status["status"] = "degraded"

    return status
