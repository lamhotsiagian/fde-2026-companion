from fastapi import APIRouter
from loguru import logger

analytics_router = APIRouter()

@analytics_router.get("/summary")
async def get_analytics_summary():
    logger.info("Fetching analytics summary")
    summary = {
        "daily_active_users": 28,
        "total_documents_processed": 128,
        "total_tokens_consumed": 485000,
        "avg_faithfulness": 0.94,
    }
    logger.debug(f"Analytics summary retrieved: {summary}")
    return summary
