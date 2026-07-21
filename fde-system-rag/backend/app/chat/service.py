import json
from collections.abc import AsyncGenerator, AsyncIterator
from uuid import UUID
from loguru import logger

from app.db.checkpointer import get_checkpointer
from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from app.config import settings

from .langgraph_agent import build_retrival_graph, create_model
from .schemas import Message, PromptInput


async def simple_chat_stream(prompt_input: PromptInput) -> AsyncGenerator:
    model = create_model(model_name=prompt_input.model_name, streaming=True)
    async for chunk in model.astream([HumanMessage(content=prompt_input.prompt)]):
        if content := chunk.content:
            response = {"type": "llm_chunk", "content": str(content)}
            yield json.dumps(response) + "\n"


async def chat_stream(thread_id: UUID, prompt_input: PromptInput, user_id: UUID) -> AsyncIterator:
    """
    Streams the agent's execution steps and final response.

    When guardrails are enabled (GUARD_ENABLED=true, the default) the free-text
    path runs through the ten-layer guarded graph in app.guardrails; slash
    commands still route to the deterministic command executors (now behind the
    L5 tool gate inside that graph). Set GUARD_ENABLED=false to fall back to the
    legacy unguarded ReAct path below.
    """
    from app.guardrails import guard_settings
    if guard_settings.enabled:
        from app.guardrails import run_guarded_stream

        async def guarded():
            async for line in run_guarded_stream(thread_id, prompt_input.prompt, user_id):
                yield line
        return guarded()

    # Intercept and route slash commands
    if prompt_input.prompt.strip().startswith("/"):
        async def cmd_stream():
            from app.course.routes import parse_slash_command, run_command_by_name
            from app.db.main import async_session
            from langchain_core.messages import AIMessage
            
            command_name, params = parse_slash_command(prompt_input.prompt)
            async with async_session() as session:
                res = await run_command_by_name(command_name, params, session, user_id)
            
            content = res.message
            if res.status == "needs_seed":
                content = f"⚠️ {res.message}\n\n*Suggested Command:* `/{res.suggested_command}` (Reason: {res.reason})"
                
            yield "messages", (AIMessage(content=content), None)
            
        return cmd_stream()

    # 1. Fetch relevant memories (Chapter 7: Context Injection)
    from app.db.main import async_session
    from app.memory.reader import search_memories, reformulate_query
    from app.memory.context_manager import inject_memories_to_prompt, manage_token_budget
    from app.memory.writer import extract_memories
    from app.memory.service import add_memory_item
    from langchain_core.messages import AIMessage
    
    # Combined search
    async with async_session() as session:
        user_memories = await search_memories(
            session=session,
            user_id=str(user_id),
            query=prompt_input.prompt,
            strategy="combined",
            limit=5
        )
    
    # Optionally reformulate query
    query = prompt_input.prompt
    if user_memories:
        query = await reformulate_query(prompt_input.prompt, user_memories, prompt_input.model_name)

    config = RunnableConfig(configurable={"thread_id": str(thread_id), "user_id": str(user_id)})
    checkpointer = await get_checkpointer()
    graph = build_retrival_graph(checkpointer, prompt_input.model_name)

    # 2. Inject context to the agent prompt context window
    injected_query = inject_memories_to_prompt(query, user_memories)

    # Run agent execution and capture outputs to trigger async write path
    async def wrapped_stream():
        full_ai_response = ""
        async for chunk_type, val in graph.astream(
            input={"messages": [HumanMessage(content=injected_query)], "retry_count": 0},
            config=config,
            stream_mode=["updates", "messages"],
        ):
            yield chunk_type, val
            
            # Capture final agent messages for memory extraction
            if chunk_type == "messages":
                message = val[0]
                if isinstance(message, (AIMessageChunk, AIMessage)) and message.content:
                    full_ai_response += str(message.content)
            elif chunk_type == "updates":
                for node_output in val.values():
                    if "messages" not in node_output:
                        continue
                    msg = node_output["messages"][-1]
                    if isinstance(msg, AIMessage) and msg.content:
                        full_ai_response += str(msg.content)
                        
        # 3. Trigger write path (Chapter 4: Extraction on turn completion)
        if full_ai_response:
            try:
                # Async extract and write to DB
                turns = [
                    HumanMessage(content=prompt_input.prompt),
                    AIMessage(content=full_ai_response)
                ]
                extracted = await extract_memories(turns, prompt_input.model_name)
                async with async_session() as session:
                    for item in extracted:
                        # Filter by salience threshold (Chapter 4)
                        if item.get("importance_score", 0.5) >= settings.memory_importance_threshold:
                            await add_memory_item(
                                session=session,
                                user_id=user_id,
                                thread_id=thread_id,
                                memory_type=item.get("memory_type", "episodic"),
                                content=item.get("content"),
                                importance_score=item.get("importance_score", 0.5),
                                metadata_json=json.dumps(item.get("metadata", {}))
                            )
            except Exception as ex:
                logger.error(f"Error in write path extraction: {ex}")

    from langchain_core.messages import AIMessageChunk
    return wrapped_stream()


async def get_chat_history(thread_id: UUID, user_id: UUID) -> list[Message]:
    config = RunnableConfig(configurable={"thread_id": str(thread_id), "user_id": str(user_id)})
    checkpointer = await get_checkpointer()
    checkpoint = await checkpointer.aget(config)

    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Chat history not found")

    all_messages = checkpoint.get("channel_values", {}).get("messages", [])
    messages = [
        Message(role=message.type, content=message.content)
        for message in all_messages
        if message.content and message.type in ["human", "ai"]
    ]

    return messages


async def resume_chat_stream(thread_id: UUID, approved: bool, user_id: UUID) -> AsyncIterator:
    """Resume a parked HITL interrupt (L5 destructive-command confirmation)."""
    from app.guardrails import resume_guarded_stream

    async def resumed():
        async for line in resume_guarded_stream(thread_id, approved, user_id):
            yield line
    return resumed()
