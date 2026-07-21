import uuid
from typing import Any
from loguru import logger
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from .base import BaseChunker

class ParentDocumentChunker(BaseChunker):
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, parent_chunk_size: int = 4000):
        super().__init__(chunk_size, chunk_overlap)
        self.parent_chunk_size = parent_chunk_size
    
    def chunk(self, text: str, metadata: dict[str, Any] | None = None) -> list[Document]:
        logger.debug(f"Chunking text of length {len(text)} with parent document strategy")
        metadata = metadata or {}
        
        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.parent_chunk_size,
            chunk_overlap=0
        )
        child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        parent_docs = parent_splitter.create_documents([text], metadatas=[metadata])
        
        all_docs = []
        
        for parent_idx, parent_doc in enumerate(parent_docs):
            parent_id = str(uuid.uuid4())
            parent_meta = parent_doc.metadata.copy()
            parent_meta.update({
                "parent_id": parent_id,
                "is_parent": True
            })
            parent_doc.metadata = parent_meta
            all_docs.append(parent_doc)
            
            child_docs = child_splitter.create_documents([parent_doc.page_content], metadatas=[metadata])
            for child_idx, child_doc in enumerate(child_docs):
                child_meta = child_doc.metadata.copy()
                child_meta.update({
                    "parent_id": parent_id,
                    "child_index": child_idx,
                    "is_parent": False
                })
                child_doc.metadata = child_meta
                all_docs.append(child_doc)
                
        return all_docs
