from fastapi import APIRouter
from .metrics import ResponseEvaluation
from uuid import uuid4
import random
from loguru import logger

evaluation_router = APIRouter()

@evaluation_router.get("/metrics", response_model=list[ResponseEvaluation])
async def get_evaluation_metrics():
    """Return recent response evaluations for the Evaluation Dashboard."""
    logger.info("Fetching evaluation metrics")
    # Return mock/live metrics data
    metrics = []
    for i in range(10):
        prompt_t = random.randint(150, 500)
        comp_t = random.randint(50, 200)
        metrics.append(ResponseEvaluation(
            query_id=str(uuid4()),
            total_latency_ms=round(random.uniform(200.0, 800.0), 2),
            embedding_time_ms=round(random.uniform(10.0, 50.0), 2),
            retrieval_time_ms=round(random.uniform(30.0, 100.0), 2),
            generation_time_ms=round(random.uniform(150.0, 600.0), 2),
            context_tokens=random.randint(500, 2000),
            prompt_tokens=prompt_t,
            completion_tokens=comp_t,
            estimated_cost_usd=round((prompt_t * 0.00000015) + (comp_t * 0.0000006), 6),
            faithfulness_score=round(random.uniform(0.85, 1.0), 2),
            answer_relevancy_score=round(random.uniform(0.88, 1.0), 2),
        ))
    logger.debug(f"Generated {len(metrics)} mock evaluation metrics")
    return metrics
