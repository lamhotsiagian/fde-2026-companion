from loguru import logger
from app.db.pgvector_utils import embeddings
import time

async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using the configured embedding model."""
    start = time.perf_counter()
    vectors = await embeddings.aembed_documents(texts)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"Embedded {len(texts)} texts in {elapsed_ms:.1f}ms")
    return vectors

async def embed_query(query: str) -> list[float]:
    """Embed a single query."""
    start = time.perf_counter()
    vector = await embeddings.aembed_query(query)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"Embedded query in {elapsed_ms:.1f}ms")
    return vector
