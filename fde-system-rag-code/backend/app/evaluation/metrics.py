from pydantic import BaseModel
import time
from loguru import logger

class ResponseEvaluation(BaseModel):
    query_id: str
    total_latency_ms: float
    embedding_time_ms: float
    retrieval_time_ms: float
    generation_time_ms: float
    context_tokens: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    faithfulness_score: float  # 0.0 - 1.0
    answer_relevancy_score: float  # 0.0 - 1.0

class MetricsCollector:
    @staticmethod
    def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
        # Local model (ollama) cost is 0.0, but calculate theoretical OpenAI pricing
        cost = (prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006)
        logger.debug(f"Estimated cost for {prompt_tokens} prompt / {completion_tokens} completion tokens: ${cost:.6f}")
        return cost
        
    @staticmethod
    def calculate_faithfulness(context: str, answer: str) -> float:
        """Calculate faithfulness score of answer relative to context."""
        if not context or not answer:
            logger.warning("Empty context or answer provided to calculate_faithfulness")
            return 1.0
        words_in_context = set(context.lower().split())
        words_in_answer = set(answer.lower().split())
        overlap = words_in_answer.intersection(words_in_context)
        score = min(1.0, len(overlap) / max(1, len(words_in_answer)))
        logger.debug(f"Faithfulness score calculated: {score:.2f}")
        return score

    @staticmethod
    def calculate_relevancy(question: str, answer: str) -> float:
        """Calculate relevancy score of answer to question."""
        if not question or not answer:
            logger.warning("Empty question or answer provided to calculate_relevancy")
            return 0.5
        q_words = set(question.lower().split())
        a_words = set(answer.lower().split())
        overlap = q_words.intersection(a_words)
        score = min(1.0, 0.5 + (len(overlap) / max(1, len(q_words))))
        logger.debug(f"Relevancy score calculated: {score:.2f}")
        return score
