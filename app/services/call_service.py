"""
Call service - Business logic for WebRTC calling system.
Supports both 1-on-1 and group calls.
"""

import logging
from typing import List, Optional, Tuple, Any, Dict
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import uuid

from app.models.call import Call, CallParticipant, CallInvitation
from app.models.user import User
from app.schemas.call import (
    CallResponse,
    CallParticipantResponse,
    CallHistoryItem,
    UserCallInfo
)
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class CallService:
    """
    Call service for managing voice and video calls.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ============================================
    # Call Initiation
    # ============================================
    
    async def initiate_call(
        self,
        initiator_id: uuid.UUID,
        participant_ids: List[uuid.UUID],
        call_type: str,
        max_participants: Optional[int] = None,
        metadata: Optional[Dict[Any, Any]] = None
    ) -> Call:
        if initiator_id in participant_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot call yourself"
            )
        
        stmt = select(User).where(
            User.id.in_(participant_ids),
            User.is_active == True
        )
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        
        if len(users) != len(participant_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more participants not found"
            )
        
        for participant_id in participant_ids:
            active_call = await self._get_active_call_between_users(
                initiator_id, participant_id
            )
            if active_call:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Already in an active call with user {participant_id}"
                )
        
        call_mode = "group" if len(participant_ids) > 1 else "1-on-1"
        
        call = Call(
            initiator_id=initiator_id,
            call_type=call_type,
            call_mode=call_mode,
            status="ringing",
            max_participants=max_participants if call_mode == "group" else None,
            started_at=datetime.now(timezone.utc),
            call_metadata=metadata if metadata is not None else {} # Fixed Attribute Name
        )
        
        self.db.add(call)
        await self.db.flush()
        
        initiator_participant = CallParticipant(
            call_id=call.id,
            user_id=initiator_id,
            role="initiator",
            status="joined",
            invited_at=datetime.now(timezone.utc),
            joined_at=datetime.now(timezone.utc),
            is_muted=False,
            is_video_enabled=(call_type == "video"),
            participant_metadata={} # Fixed Attribute Name
        )
        self.db.add(initiator_participant)
        
        for participant_id in participant_ids:
            participant = CallParticipant(
                call_id=call.id,
                user_id=participant_id,
                role="participant",
                status="ringing",
                invited_at=datetime.now(timezone.utc),
                is_muted=False,
                is_video_enabled=(call_type == "video"),
                participant_metadata={} # Fixed Attribute Name
            )
            self.db.add(participant)
        
        await self.db.commit()
        await self.db.refresh(call)
        
        logger.info(f"Call initiated: {call.id} by {initiator_id}")
        return call
    
    # ============================================
    # Call Actions
    # ============================================
    
    async def answer_call(
        self,
        call_id: uuid.UUID,
        user_id: uuid.UUID,
        metadata: Optional[Dict[Any, Any]] = None
    ) -> Call:
        call = await self._get_call_with_participants(call_id)
        
        if not call:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
        
        if call.status not in ["ringing", "active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot join call with status: {call.status}"
            )
        
        participant = next((p for p in call.participants if p.user_id == user_id), None)
        
        if not participant:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")
        
        if participant.status not in ["ringing"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot answer now")
        
        participant.status = "joined"
        participant.joined_at = datetime.now(timezone.utc)
        
        if metadata is not None:
            if participant.participant_metadata is None: # Fixed Attribute Name
                participant.participant_metadata = {}
            participant.participant_metadata.update(metadata)
        
        if call.status == "ringing":
            call.status = "active"
        
        await self.db.commit()
        await self.db.refresh(call)
        return call
    
    async def decline_call(self, call_id: uuid.UUID, user_id: uuid.UUID, reason: str = "declined") -> Call:
        call = await self._get_call_with_participants(call_id)
        if not call:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
        
        participant = next((p for p in call.participants if p.user_id == user_id), None)
        if not participant or participant.status != "ringing":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot decline")
        
        participant.status = "declined"
        if call.call_mode == "1-on-1":
            call.status = "declined"
            call.ended_at = datetime.now(timezone.utc)
            call.ended_by = user_id
            call.end_reason = reason
        elif call.call_mode == "group":
            all_declined = all(p.status in ["declined", "missed"] for p in call.participants if p.role == "participant")
            if all_declined:
                call.status = "declined"
                call.ended_at = datetime.now(timezone.utc)
                call.end_reason = "all_declined"
        
        await self.db.commit()
        await self.db.refresh(call)
        return call
    
    async def end_call(self, call_id: uuid.UUID, user_id: uuid.UUID, reason: str = "user_hangup") -> Call:
        call = await self._get_call_with_participants(call_id)
        if not call:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
        
        participant = next((p for p in call.participants if p.user_id == user_id), None)
        if not participant:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")
        
        if participant.status == "joined":
            participant.status = "left"
            participant.left_at = datetime.now(timezone.utc)
        
        if call.call_mode == "1-on-1":
            call.status = "ended"
            call.ended_at = datetime.now(timezone.utc)
            call.ended_by = user_id
            call.end_reason = reason
            for p in call.participants:
                if p.user_id != user_id and p.status == "joined":
                    p.status = "left"
                    p.left_at = datetime.now(timezone.utc)
        elif call.call_mode == "group":
            active_participants = [p for p in call.participants if p.status == "joined" and p.user_id != user_id]
            if not active_participants:
                call.status = "ended"
                call.ended_at = datetime.now(timezone.utc)
                call.ended_by = user_id
                call.end_reason = "all_left"
        
        await self.db.commit()
        await self.db.refresh(call)
        return call
    
    # ============================================
    # Group Call Management
    # ============================================
    
    async def invite_to_call(self, call_id: uuid.UUID, inviter_id: uuid.UUID, user_ids: List[uuid.UUID]) -> List[CallParticipant]:
        call = await self._get_call_with_participants(call_id)
        if not call or call.call_mode != "group" or call.status != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid call state for invite")
        
        inviter_participant = next((p for p in call.participants if p.user_id == inviter_id), None)
        if not inviter_participant or inviter_participant.status != "joined":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only active participants can invite")
        
        if call.max_participants and len(call.participants) + len(user_ids) > call.max_participants:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exceeds max participants")
        
        stmt = select(User).where(User.id.in_(user_ids), User.is_active == True)
        users = (await self.db.execute(stmt)).scalars().all()
        if len(users) != len(user_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Some users not found")
        
        new_participants = []
        for user_id in user_ids:
            if any(p.user_id == user_id for p in call.participants):
                continue
            
            participant = CallParticipant(
                call_id=call_id,
                user_id=user_id,
                role="participant",
                status="ringing",
                invited_at=datetime.now(timezone.utc),
                is_muted=False,
                is_video_enabled=(call.call_type == "video"),
                participant_metadata={} # Fixed Attribute Name
            )
            self.db.add(participant)
            new_participants.append(participant)
            
            invitation = CallInvitation(
                call_id=call_id,
                invited_user_id=user_id,
                invited_by=inviter_id,
                status="pending",
                invited_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=2)
            )
            self.db.add(invitation)
        
        await self.db.commit()
        return new_participants
    
    # ============================================
    # Media & Queries
    # ============================================
    
    async def update_media_state(self, call_id: uuid.UUID, user_id: uuid.UUID, is_muted: Optional[bool] = None, is_video_enabled: Optional[bool] = None, is_screen_sharing: Optional[bool] = None) -> CallParticipant:
        stmt = select(CallParticipant).where(CallParticipant.call_id == call_id, CallParticipant.user_id == user_id)
        participant = (await self.db.execute(stmt)).scalar_one_or_none()
        
        if not participant or participant.status != "joined":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active participant not found")
        
        if is_muted is not None: participant.is_muted = is_muted
        if is_video_enabled is not None: participant.is_video_enabled = is_video_enabled
        if is_screen_sharing is not None: participant.is_screen_sharing = is_screen_sharing
        
        await self.db.commit()
        await self.db.refresh(participant)
        return participant
    
    async def get_call_by_id(self, call_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Call]:
        call = await self._get_call_with_participants(call_id)
        if call and any(p.user_id == user_id for p in call.participants):
            return call
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    async def get_call_history(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Call], int]:
        stmt = select(Call).join(CallParticipant).where(CallParticipant.user_id == user_id).options(selectinload(Call.participants).selectinload(CallParticipant.user), selectinload(Call.initiator)).order_by(desc(Call.started_at))
        count_stmt = select(func.count()).select_from(select(Call.id).join(CallParticipant).where(CallParticipant.user_id == user_id).subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        calls = (await self.db.execute(stmt.limit(limit).offset(offset))).scalars().all()
        return list(calls), total
    
    async def get_active_calls(self, user_id: uuid.UUID) -> List[Call]:
        stmt = select(Call).join(CallParticipant).where(CallParticipant.user_id == user_id, CallParticipant.status == "joined", Call.status.in_(["ringing", "active"])).options(selectinload(Call.participants).selectinload(CallParticipant.user), selectinload(Call.initiator))
        return list((await self.db.execute(stmt)).scalars().all())
    
    async def _get_call_with_participants(self, call_id: uuid.UUID) -> Optional[Call]:
        stmt = select(Call).where(Call.id == call_id).options(selectinload(Call.participants).selectinload(CallParticipant.user), selectinload(Call.initiator))
        return (await self.db.execute(stmt)).scalar_one_or_none()
    
    async def _get_active_call_between_users(self, user1_id: uuid.UUID, user2_id: uuid.UUID) -> Optional[Call]:
        stmt = select(Call).join(CallParticipant).where(Call.status.in_(["ringing", "active"]), Call.call_mode == "1-on-1", CallParticipant.user_id.in_([user1_id, user2_id])).group_by(Call.id).having(func.count(CallParticipant.id) == 2)
        return (await self.db.execute(stmt)).scalar_one_or_none()