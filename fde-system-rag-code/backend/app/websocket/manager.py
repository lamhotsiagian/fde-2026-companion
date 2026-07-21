from fastapi import WebSocket
from loguru import logger
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, thread_id: str):
        await websocket.accept()
        if thread_id not in self.active_connections:
            self.active_connections[thread_id] = []
        self.active_connections[thread_id].append(websocket)
        logger.info(f"WebSocket connected for thread {thread_id}")

    def disconnect(self, websocket: WebSocket, thread_id: str):
        if thread_id in self.active_connections:
            self.active_connections[thread_id].remove(websocket)
            if not self.active_connections[thread_id]:
                del self.active_connections[thread_id]
        logger.info(f"WebSocket disconnected for thread {thread_id}")

    async def broadcast(self, thread_id: str, message: dict):
        if thread_id in self.active_connections:
            for connection in self.active_connections[thread_id]:
                await connection.send_json(message)

manager = ConnectionManager()
