from typing import Any
from loguru import logger
from langchain_core.documents import Document
from .base import BaseChunker

class SlidingWindowChunker(BaseChunker):
    def chunk(self, text: str, metadata: dict[str, Any] | None = None) -> list[Document]:
        logger.debug(f"Chunking text of length {len(text)} with sliding window strategy")
        metadata = metadata or {}
        
        step = max(1, self.chunk_size - self.chunk_overlap)
        chunks = []
        
        for i in range(0, len(text), step):
            window_text = text[i:i + self.chunk_size]
            chunks.append(Document(page_content=window_text, metadata=metadata.copy()))
            if i + self.chunk_size >= len(text):
                break
                
        return chunks
