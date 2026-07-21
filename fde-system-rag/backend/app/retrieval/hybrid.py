from uuid import UUID
from langchain_core.documents import Document
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import time

from .bm25 import bm25_search
from .vector_search import vector_search

class HybridRetriever:
    def __init__(self, bm25_weight: float = 0.3, vector_weight: float = 0.7):
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
    
    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        k: int = 10,
        tenant_id: UUID | None = None,
        thread_id: UUID | None = None,
        use_reranker: bool = True,
    ) -> list[Document]:
        """Perform hybrid retrieval: BM25 + Vector + optional Reranker."""
        start = time.perf_counter()
        
        # 1. Retrieve from both sources (fetch more candidates for reranking)
        candidate_k = k * 3
        
        bm25_results = await bm25_search(query, session, k=candidate_k, tenant_id=tenant_id, thread_id=thread_id)
        vector_results = await vector_search(query, k=candidate_k, tenant_id=tenant_id, thread_id=thread_id)
        
        # 2. Reciprocal Rank Fusion (RRF) to merge results
        merged = self._reciprocal_rank_fusion(bm25_results, vector_results)
        
        # 3. Optional reranking
        if use_reranker and merged:
            from app.reranker.service import rerank
            merged = await rerank(query, merged, top_k=k)
        else:
            merged = merged[:k]
        
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Hybrid retrieval returned {len(merged)} results in {elapsed_ms:.1f}ms")
        return merged
    
    def _reciprocal_rank_fusion(self, *result_lists: list[Document], rrf_k: int = 60) -> list[Document]:
        """Merge multiple result lists using Reciprocal Rank Fusion."""
        doc_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}
        
        for results in result_lists:
            for rank, doc in enumerate(results):
                # Use page_content hash as unique key
                doc_key = str(hash(doc.page_content))
                if doc_key not in doc_scores:
                    doc_scores[doc_key] = 0.0
                    doc_map[doc_key] = doc
                doc_scores[doc_key] += 1.0 / (rrf_k + rank + 1)
        
        # Sort by RRF score descending
        sorted_keys = sorted(doc_scores.keys(), key=lambda k: doc_scores[k], reverse=True)
        
        merged = []
        for key in sorted_keys:
            doc = doc_map[key]
            doc.metadata["rrf_score"] = doc_scores[key]
            merged.append(doc)
        
        return merged
