from mcp.server.fastmcp import FastMCP
from app.db.main import async_session
from app.memory.reader import search_memories
from uuid import UUID

# Initialize FastMCP Server
mcp = FastMCP("LocalMemoryServer")

@mcp.tool()
async def search_user_memories(user_id: str, query: str, strategy: str = "combined") -> str:
    """
    Query the localized RAG episodic and semantic memory layers for a specific user.
    """
    try:
        user_uuid = UUID(user_id)
        async with async_session() as session:
            results = await search_memories(
                session=session,
                user_id=str(user_uuid),
                query=query,
                strategy=strategy,
                limit=5
            )
        
        if not results:
            return "No matching memories found."
            
        mem_text = "\n".join([f"- {r['memory'].content} (Score: {r['final_score']:.3f})" for r in results])
        return f"Retrieved Memories:\n{mem_text}"
    except Exception as e:
        return f"Error executing memory search: {str(e)}"

# Start this server using: fastmcp run backend/app/memory/mcp_server.py
