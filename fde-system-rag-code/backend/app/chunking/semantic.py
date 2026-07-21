import re
from typing import Any
from loguru import logger
from langchain_core.documents import Document
from .base import BaseChunker

class SemanticChunker(BaseChunker):
    def chunk(self, text: str, metadata: dict[str, Any] | None = None) -> list[Document]:
        logger.debug(f"Chunking text of length {len(text)} with semantic strategy")
        metadata = metadata or {}
        
        # Simple regex to split on sentences
        sentences = re.split(r'(?<=[.?!])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += (sentence + " ")
            else:
                if current_chunk:
                    chunks.append(Document(page_content=current_chunk.strip(), metadata=metadata.copy()))
                # If a single sentence is larger than chunk_size, we just add it
                current_chunk = sentence + " "
                
        if current_chunk:
            chunks.append(Document(page_content=current_chunk.strip(), metadata=metadata.copy()))
            
        return chunks
