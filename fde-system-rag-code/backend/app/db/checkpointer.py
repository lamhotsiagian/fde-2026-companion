from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

_checkpointer: MemorySaver | None = None

async def get_checkpointer() -> MemorySaver:
    global _checkpointer
    if _checkpointer is None:
        logger.info("Initializing MemorySaver checkpointer...")
        _checkpointer = MemorySaver()
    return _checkpointer

async def create_connection():
    """No-op kept for backwards compatibility in external script imports."""
    pass

async def close_connection() -> None:
    """No-op kept for backwards compatibility in external script imports."""
    pass
