from typing import Any
from loguru import logger
from langchain_text_splitters import MarkdownTextSplitter
from langchain_core.documents import Document
from .base import BaseChunker

class MarkdownChunker(BaseChunker):
    def chunk(self, text: str, metadata: dict[str, Any] | None = None) -> list[Document]:
        logger.debug(f"Chunking text of length {len(text)} with markdown strategy")
        splitter = MarkdownTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        metadata = metadata or {}
        return splitter.create_documents([text], metadatas=[metadata])
