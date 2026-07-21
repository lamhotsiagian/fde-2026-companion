from typing import Any
from .base import BaseChunker

CHUNKER_REGISTRY: dict[str, type[BaseChunker]] = {}

def get_chunker(strategy: str = "recursive", chunk_size: int = 1000, chunk_overlap: int = 200, **kwargs: Any) -> BaseChunker:
    """Get a chunker by strategy name."""
    from .recursive import RecursiveChunker
    from .semantic import SemanticChunker
    from .parent_document import ParentDocumentChunker
    from .markdown_chunker import MarkdownChunker
    from .sliding_window import SlidingWindowChunker
    
    registry = {
        "recursive": RecursiveChunker,
        "semantic": SemanticChunker,
        "parent_document": ParentDocumentChunker,
        "markdown": MarkdownChunker,
        "sliding_window": SlidingWindowChunker,
    }
    
    chunker_cls = registry.get(strategy)
    if chunker_cls is None:
        raise ValueError(f"Unknown chunking strategy: {strategy}. Available: {list(registry.keys())}")
    return chunker_cls(chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs)
