# This file makes 'models' a Python package
from messaging_sdk.models.user import User
from messaging_sdk.database import Base
from messaging_sdk.models.contact import Contact  # <--- This is the missing link
from messaging_sdk.models.message import Conversation, Message, ConversationParticipant

__all__ = ["User"]