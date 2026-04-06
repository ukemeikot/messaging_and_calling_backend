"""
WebSocket connection manager for real-time call signaling.
Manages active WebSocket connections and message routing.
"""

import logging
import json
from typing import Dict, Set, Optional
from fastapi import WebSocket
import uuid

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for call signaling.
    
    Features:
    - Track active connections per user
    - Route messages between peers
    - Handle disconnections
    - Broadcast to call participants
    """
    
    def __init__(self):
        # user_id -> set of WebSocket connections (supports multiple devices)
        self.active_connections: Dict[uuid.UUID, Set[WebSocket]] = {}
        
        # call_id -> set of user_ids in that call
        self.call_participants: Dict[uuid.UUID, Set[uuid.UUID]] = {}
        
        # websocket -> user_id mapping for quick lookup
        self.connection_to_user: Dict[WebSocket, uuid.UUID] = {}
    
    async def connect(self, websocket: WebSocket, user_id: uuid.UUID):
        """
        Register a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            user_id: User ID
        """
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        self.connection_to_user[websocket] = user_id
        
        logger.info(f"WebSocket connected: user={user_id}, total_connections={len(self.active_connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket):
        """
        Unregister a WebSocket connection.
        
        Args:
            websocket: WebSocket connection to remove
        """
        if websocket not in self.connection_to_user:
            return
        
        user_id = self.connection_to_user[websocket]
        
        # Remove from active connections
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            
            # Remove user entry if no more connections
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # Remove from lookup
        del self.connection_to_user[websocket]
        
        logger.info(f"WebSocket disconnected: user={user_id}")
    
    def add_to_call(self, call_id: uuid.UUID, user_id: uuid.UUID):
        """
        Add user to a call's participant list.
        
        Args:
            call_id: Call ID
            user_id: User ID
        """
        if call_id not in self.call_participants:
            self.call_participants[call_id] = set()
        
        self.call_participants[call_id].add(user_id)
        logger.debug(f"Added user {user_id} to call {call_id}")
    
    def remove_from_call(self, call_id: uuid.UUID, user_id: uuid.UUID):
        """
        Remove user from a call's participant list.
        
        Args:
            call_id: Call ID
            user_id: User ID
        """
        if call_id in self.call_participants:
            self.call_participants[call_id].discard(user_id)
            
            # Clean up empty call
            if not self.call_participants[call_id]:
                del self.call_participants[call_id]
        
        logger.debug(f"Removed user {user_id} from call {call_id}")
    
    async def send_personal_message(
        self,
        message: dict,
        user_id: uuid.UUID
    ):
        """
        Send message to a specific user (all their devices).
        
        Args:
            message: Message dict to send
            user_id: Target user ID
        """
        if user_id not in self.active_connections:
            logger.warning(f"User {user_id} has no active connections")
            return
        
        message_json = json.dumps(message)
        disconnected = set()
        
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Failed to send to user {user_id}: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected sockets
        for connection in disconnected:
            self.disconnect(connection)
    
    async def send_to_call(
        self,
        message: dict,
        call_id: uuid.UUID,
        exclude_user_id: Optional[uuid.UUID] = None
    ):
        """
        Broadcast message to all participants in a call.
        
        Args:
            message: Message dict to send
            call_id: Call ID
            exclude_user_id: Optional user to exclude (e.g., sender)
        """
        if call_id not in self.call_participants:
            logger.warning(f"Call {call_id} has no participants")
            return
        
        participants = self.call_participants[call_id]
        
        for user_id in participants:
            if exclude_user_id and user_id == exclude_user_id:
                continue
            
            await self.send_personal_message(message, user_id)
    
    async def send_to_peer(
        self,
        message: dict,
        from_user_id: uuid.UUID,
        to_user_id: uuid.UUID,
        call_id: uuid.UUID
    ):
        """
        Send WebRTC signaling message between two peers.
        
        Args:
            message: Signaling message (SDP/ICE)
            from_user_id: Sender user ID
            to_user_id: Recipient user ID
            call_id: Call ID
        """
        # Verify both users are in the call
        if call_id not in self.call_participants:
            logger.warning(f"Call {call_id} not found")
            return
        
        participants = self.call_participants[call_id]
        
        if from_user_id not in participants or to_user_id not in participants:
            logger.warning(
                f"User(s) not in call {call_id}: "
                f"from={from_user_id in participants}, to={to_user_id in participants}"
            )
            return
        
        # Add metadata
        message["from_user_id"] = str(from_user_id)
        message["call_id"] = str(call_id)
        
        await self.send_personal_message(message, to_user_id)
    
    def get_call_participant_count(self, call_id: uuid.UUID) -> int:
        """
        Get number of participants in a call.
        
        Args:
            call_id: Call ID
            
        Returns:
            Number of participants
        """
        if call_id not in self.call_participants:
            return 0
        return len(self.call_participants[call_id])
    
    def is_user_online(self, user_id: uuid.UUID) -> bool:
        """
        Check if user has any active WebSocket connections.
        
        Args:
            user_id: User ID
            
        Returns:
            True if user is connected
        """
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0
    
    def get_online_users(self) -> Set[uuid.UUID]:
        """
        Get set of all currently online user IDs.
        
        Returns:
            Set of user IDs
        """
        return set(self.active_connections.keys())
    
    def get_connection_count(self) -> int:
        """
        Get total number of active WebSocket connections.
        
        Returns:
            Total connection count
        """
        return sum(len(connections) for connections in self.active_connections.values())


# Global connection manager instance
manager = ConnectionManager()