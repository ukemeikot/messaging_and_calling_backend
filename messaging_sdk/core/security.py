"""
Security utilities for password hashing and JWT token management.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import os
import secrets
from typing import Optional
import uuid

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain text password using Argon2."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    raise ValueError(
        "SECRET_KEY not found in environment variables. "
        "Please check your .env file."
    )

SECRET_KEY: str = _secret_key
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))


class TokenType(str, Enum):
    REFRESH = "refresh"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


def _state_fingerprint(value: str) -> str:
    """Create a stable fingerprint for short-lived token state binding."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token for authentication."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token for obtaining new access tokens."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": TokenType.REFRESH.value})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def create_verification_token(user_id: uuid.UUID, email: str) -> str:
    """Create an email verification token."""
    expire_hours = int(os.getenv("VERIFICATION_TOKEN_EXPIRE_HOURS", "24"))
    expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    token_data = {
        "user_id": str(user_id),
        "email": email,
        "type": TokenType.EMAIL_VERIFICATION.value,
        "jti": secrets.token_urlsafe(16),
        "exp": expire,
    }
    return jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)


def verify_verification_token(token: str) -> dict:
    """Verify and decode an email verification token."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != TokenType.EMAIL_VERIFICATION.value:
        raise JWTError("Invalid token type")
    return {
        "user_id": payload.get("user_id"),
        "email": payload.get("email"),
        "jti": payload.get("jti"),
    }


def create_password_reset_token(user_id: uuid.UUID, email: str, password_state: str) -> str:
    """Create a password reset token bound to the user's current password state."""
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    token_data = {
        "user_id": str(user_id),
        "email": email,
        "type": TokenType.PASSWORD_RESET.value,
        "jti": secrets.token_urlsafe(16),
        "pwd": _state_fingerprint(password_state),
        "exp": expire,
    }
    return jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)


def verify_password_reset_token(token: str) -> dict:
    """Verify and decode a password reset token."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != TokenType.PASSWORD_RESET.value:
        raise JWTError("Invalid token type")
    return {
        "user_id": payload.get("user_id"),
        "email": payload.get("email"),
        "jti": payload.get("jti"),
        "pwd": payload.get("pwd"),
    }


def password_reset_state_matches(token_state: Optional[str], password_state: str) -> bool:
    """Check whether a reset token still matches the current password state."""
    if not token_state:
        return False
    return secrets.compare_digest(token_state, _state_fingerprint(password_state))
