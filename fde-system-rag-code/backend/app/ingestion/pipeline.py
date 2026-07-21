import time
import re
import unicodedata
from pathlib import Path
from uuid import UUID
from loguru import logger

from app.ingestion.extractors import get_extractor
from app.chunking import get_chunker
from app.embedding import embed_texts

async def process_document(
    file_path: Path,
    document_id: UUID,
    thread_id: UUID,
    user_id: UUID,
    tenant_id: UUID | None,
    chunking_strategy: str = "recursive",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> dict:
    start_time = time.perf_counter()
    logger.info(f"Starting processing for document {document_id}")
    
    # 1. Extract text using extractors.py
    extractor = get_extractor(file_path)
    raw_text = await extractor.extract(file_path)
    
    # 2. Clean the extracted text (remove extra whitespace, normalize unicode)
    clean_text = re.sub(r'\s+', ' ', raw_text).strip()
    clean_text = unicodedata.normalize('NFKC', clean_text)
    
    # 3. Extract metadata
    file_size = file_path.stat().st_size if file_path.exists() else 0
    word_count = len(clean_text.split())
    # Note: For page count, could potentially retrieve from PDFExtractor if we updated the interface, 
    # but for now we'll stick to basic metadata
    metadata = {
        "file_size": file_size,
        "word_count": word_count,
        "language": "en"  # language detection placeholder
    }
    
    # 4. Chunk using the specified strategy
    chunker = get_chunker(chunking_strategy)
    chunks = chunker.chunk(clean_text, chunk_size, chunk_overlap)
    
    # 5. Generate embeddings
    embeddings = await embed_texts(chunks)
    
    # 6. Store in pgvector with full metadata
    # Placeholder for pgvector storage logic with sqlalchemy async session
    logger.info(f"Storing {len(chunks)} chunks for document {document_id} into pgvector...")
    # Example logic:
    # async with AsyncSessionLocal() as session:
    #     for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
    #         # session.add(DocumentChunk(tenant_id=..., user_id=..., thread_id=..., document_id=..., chunk_index=idx, ...))
    #     await session.commit()
    
    # 7. Return a summary dict
    processing_time_ms = (time.perf_counter() - start_time) * 1000
    estimated_tokens = int(word_count * 1.3)
    
    result = {
        "document_id": str(document_id),
        "chunk_count": len(chunks),
        "total_tokens": estimated_tokens,
        "processing_time_ms": processing_time_ms,
    }
    
    logger.info(f"Finished processing document {document_id} in {processing_time_ms:.2f} ms")
    return result
