from abc import ABC, abstractmethod
from typing import Any
from langchain_core.documents import Document

class BaseChunker(ABC):
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    @abstractmethod
    def chunk(self, text: str, metadata: dict[str, Any] | None = None) -> list[Document]:
        """Split text into chunks and return as LangChain Documents."""
        ...
