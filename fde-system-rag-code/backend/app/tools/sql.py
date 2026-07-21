from langchain_core.tools import tool
from sqlalchemy import text
from loguru import logger

@tool
async def sql_tool(query: str) -> str:
    """Execute a read-only SQL SELECT query against the PostgreSQL database."""
    clean_q = query.strip().lower()
    if not clean_q.startswith("select") and not clean_q.startswith("with"):
        return "Error: Only read-only SELECT queries are allowed."
    
    try:
        from app.db.main import engine
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchmany(50)
            cols = result.keys()
            formatted = [dict(zip(cols, row)) for row in rows]
            return f"Query returned {len(formatted)} rows:\n{formatted}"
    except Exception as e:
        return f"SQL Execution error: {e}"
