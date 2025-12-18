# This file makes 'models' a Python package
from app.models.user import User
from app.database import Base
from app.models.contact import Contact  # <--- This is the missing link
from app.models.message import Conversation, Message, ConversationParticipant

__all__ = ["User"]