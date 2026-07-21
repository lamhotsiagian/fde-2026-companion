from typing import Any
from loguru import logger
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from .base import BaseChunker

class RecursiveChunker(BaseChunker):
    def chunk(self, text: str, metadata: dict[str, Any] | None = None) -> list[Document]:
        logger.debug(f"Chunking text of length {len(text)} with recursive strategy")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        metadata = metadata or {}
        return splitter.create_documents([text], metadatas=[metadata])
