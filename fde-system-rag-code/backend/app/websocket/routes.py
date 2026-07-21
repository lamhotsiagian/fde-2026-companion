from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from .manager import manager
from loguru import logger
import json, asyncio

websocket_router = APIRouter()

@websocket_router.websocket("/ws/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    await manager.connect(websocket, thread_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Parse query and stream response back
            req = json.loads(data)
            prompt = req.get("prompt", "")
            
            # Send initial ACK
            await websocket.send_json({"type": "ack", "status": "processing"})
            
            # Stream response chunks
            from app.agents.graph import build_enterprise_agent_graph
            graph = build_enterprise_agent_graph()
            
            async for event in graph.astream({"question": prompt, "step_count": 0}):
                await websocket.send_json({"type": "event", "data": event})
                
            await websocket.send_json({"type": "complete", "status": "done"})
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, thread_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, thread_id)

@websocket_router.get("/sse/{thread_id}")
async def sse_endpoint(thread_id: str, prompt: str):
    """Server-Sent Events streaming endpoint."""
    async def event_generator():
        from app.agents.graph import build_enterprise_agent_graph
        graph = build_enterprise_agent_graph()
        
        yield f"data: {json.dumps({'type': 'start', 'thread_id': thread_id})}\n\n"
        
        async for event in graph.astream({"question": prompt, "step_count": 0}):
            yield f"data: {json.dumps({'type': 'event', 'data': event})}\n\n"
            await asyncio.sleep(0.05)
            
        yield f"data: {json.dumps({'type': 'end'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
