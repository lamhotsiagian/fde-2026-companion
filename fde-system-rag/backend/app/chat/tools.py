from app.config import settings
from app.db.pgvector_utils import vector_store
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from loguru import logger

# Conditional Tavily search tool (Chapter 1)
tavily = None
if settings.tavily_api_key:
    tavily = TavilySearchResults(
        tavily_api_key=settings.tavily_api_key,
        max_results=3,
        include_answer=False,
        include_raw_content=False,
        include_images=False,
    )


@tool
async def retrieve_user_documents(query: str, config: RunnableConfig) -> str:
    """
    Use this tool to answer questions about the user's uploaded documents.
    It will automatically retrieve documents relevant to the current user and thread.
    """
    user_id = config["configurable"].get("user_id")  # type: ignore
    thread_id = config["configurable"].get("thread_id")  # type: ignore
    logger.info(f"Retrieving documents for user_id: {user_id} and thread_id: {thread_id}")

    retriever = vector_store.as_retriever(search_kwargs={"k": 3, "filter": {"thread_id": thread_id}})
    result_docs = await retriever.ainvoke(query)

    if not result_docs:
        return "No relevant documents"

    return "\n\n".join([doc.page_content for doc in result_docs])


@tool
async def recall_memories(query: str, config: RunnableConfig) -> str:
    """
    Use this tool to search the agent's personalized episodic, semantic, procedural, 
    and entity memory banks for background context or past facts about the user.
    """
    user_id = config["configurable"].get("user_id")
    if not user_id:
        return "No personalized memory session is active."
        
    from app.db.main import async_session
    from app.memory.reader import search_memories
    
    async with async_session() as session:
        results = await search_memories(
            session=session,
            user_id=str(user_id),
            query=query,
            strategy="combined",
            limit=5
        )
        
    if not results:
        return "No relevant user memories found."
        
    out = []
    for item in results:
        m = item["memory"]
        out.append(f"- [{m.memory_type.upper()}] {m.content} (Importance: {m.importance_score})")
    return "\n".join(out)


tools = [retrieve_user_documents, recall_memories]
if tavily:
    tools.append(tavily)
