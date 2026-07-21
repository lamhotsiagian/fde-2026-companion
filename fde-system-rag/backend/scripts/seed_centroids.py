"""Seed chapter_centroids from the 10 course-chapter summaries.

Run once after the guardrails migration:

    python -m scripts.seed_centroids

Embeds each chapter summary with nomic-embed-text (768-dim, the same model
and dimension as every other pgvector table in the app) and upserts one
centroid row per chapter. The L3 intent guard and L4 topic-boundary check
both query this table.
"""

import asyncio

from langchain_ollama import OllamaEmbeddings
from sqlalchemy import text as sql

from app.config import settings
from app.db.main import async_session

CHAPTER_SUMMARIES: dict[int, tuple[str, str]] = {
    1: ("Explicit vs Implicit Signals",
        "Explicit feedback ratings reviews versus implicit feedback clicks views "
        "purchases dwell time; signal strength, confidence weighting, feedback loops "
        "in recommender systems."),
    2: ("Collaborative Filtering",
        "User-user and item-item collaborative filtering, cosine similarity, rating "
        "vectors, neighborhoods, sparsity, similarity matrices for recommendations."),
    3: ("Content-Based Filtering",
        "Item features, TF-IDF, user profiles built from consumed item features, "
        "content similarity, cold-start advantages of content-based recommenders."),
    4: ("Hybrid Systems",
        "Weighted blending of collaborative and content-based scores, switching "
        "hybrids, feature augmentation, when hybrids beat single-strategy systems."),
    5: ("Knowledge-Based and Cold-Start",
        "Cold-start users and items, onboarding questionnaires, knowledge-based "
        "constraints, warm-start transitions, exploration bandits epsilon-greedy."),
    6: ("Recommender Evaluation",
        "Offline evaluation, train-test splits, RMSE, precision at k, recall, "
        "hit rate HR@10, NDCG@10, coverage, diversity, online A/B testing."),
    7: ("Neural and Sequential Models",
        "Markov chain transitions, session-based recommendation, two-tower neural "
        "retrieval, embeddings, in-batch negatives, sequence-aware recommenders."),
    8: ("Candidate Generation and ANN",
        "Approximate nearest neighbors, HNSW, IVFFlat, pgvector indexing, "
        "candidate generation funnels, recall versus latency, MMR re-ranking."),
    9: ("Matrix Factorization Capstone",
        "SGD matrix factorization, latent factors, user and item embeddings, "
        "regularization, learning-rate schedules, full recommender capstone."),
    10: ("Production Serving and MLOps",
         "Caching, model versioning, retraining pipelines, feature parity between "
         "offline and online, monitoring, drift detection, serving latency budgets."),
}


async def seed_centroids() -> None:
    embedder = OllamaEmbeddings(
        model=settings.embeddings_model_name,
        base_url=settings.embeddings_base_url,
    )
    async with async_session() as session:
        for chapter, (title, summary) in CHAPTER_SUMMARIES.items():
            embedding = await embedder.aembed_query(f"{title}. {summary}")
            await session.execute(
                sql("""
                    INSERT INTO chapter_centroids (chapter, title, embedding, updated_at)
                    VALUES (:c, :t, CAST(:e AS vector), now())
                    ON CONFLICT (chapter) DO UPDATE
                        SET title = :t, embedding = CAST(:e AS vector),
                            updated_at = now()
                """),
                {"c": chapter, "t": title, "e": str(embedding)},
            )
        await session.commit()
    print(f"Seeded {len(CHAPTER_SUMMARIES)} chapter centroids.")


if __name__ == "__main__":
    asyncio.run(seed_centroids())
