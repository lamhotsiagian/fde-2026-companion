from langchain_core.tools import tool
from pathlib import Path
import os

@tool
def filesystem_tool(operation: str, path: str = ".") -> str:
    """Perform safe filesystem operations. Operations: 'list', 'read', 'info'."""
    try:
        target = Path(path).resolve()
        if operation == "list":
            if not target.is_dir():
                return f"{path} is not a directory."
            items = os.listdir(target)
            return f"Contents of {path}: {items[:50]}"
        elif operation == "read":
            if not target.is_file():
                return f"{path} is not a file."
            text = target.read_text(encoding="utf-8")[:2000]
            return f"Content of {path} (first 2000 chars):\n{text}"
        elif operation == "info":
            stat = target.stat()
            return f"File info for {path}: Size={stat.st_size} bytes, Mode={stat.st_mode}"
        else:
            return f"Unknown operation: {operation}. Supported: list, read, info"
    except Exception as e:
        return f"Filesystem error: {e}"
