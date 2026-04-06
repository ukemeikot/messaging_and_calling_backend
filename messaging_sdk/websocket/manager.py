"""
WebSocket Manager.
"""
from fastapi import WebSocket
from typing import Dict, List
import uuid
import json
import logging

logger = logging.getLogger("websocket")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[uuid.UUID, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: uuid.UUID):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected")

    def disconnect(self, websocket: WebSocket, user_id: uuid.UUID):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_conversation(self, message: dict, participant_ids: List[uuid.UUID]):
        """Broadcast message to all online participants."""
        message_json = json.dumps(message, default=str)
        
        for pid in participant_ids:
            if pid in self.active_connections:
                for connection in self.active_connections[pid]:
                    try:
                        await connection.send_text(message_json)
                    except Exception as e:
                        logger.error(f"Error sending to {pid}: {e}")

manager = ConnectionManager()