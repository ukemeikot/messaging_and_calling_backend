"""
Security utilities for password hashing and JWT token management.
This module handles all authentication-related security operations.
"""

from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import os
from dotenv import load_dotenv
import uuid
from enum import Enum  # ✅ ADDED

load_dotenv()

# ============================================
# PASSWORD HASHING
# ============================================

# Create password context with bcrypt
# bcrypt is the industry standard for password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    
    Args:
        password: Plain text password from user
        
    Returns:
        Hashed password string (irreversible)
        
    Example:
        Input:  "MyPassword123"
        Output: "$2b$12$KIXxL5vZ9fQ7X8pN..."
        
    Security:
        - Uses bcrypt with automatic salt generation
        - Cost factor: 12 rounds (recommended for 2024)
        - Each hash is unique even for same password
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.
    
    Args:
        plain_password: Password user entered during login
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
        
    Example:
        plain = "MyPassword123"
        hashed = "$2b$12$KIXxL5vZ9fQ7X8pN..."
        verify_password(plain, hashed) → True
        
    Security:
        - Constant-time comparison (prevents timing attacks)
        - Never reveals why verification failed
    """
    return pwd_context.verify(plain_password, hashed_password)

# ============================================
# JWT TOKEN MANAGEMENT
# ============================================

# Get configuration from environment
_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    raise ValueError(
        "SECRET_KEY not found in environment variables. "
        "Please check your .env file."
    )

# Now we know it's definitely a string
SECRET_KEY: str = _secret_key
ALGORITHM = os.getenv("ALGORITHM", "HS256")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# ============================================
# TOKEN TYPES (ENUM)  # ✅ ADDED
# ============================================

class TokenType(str, Enum):
    REFRESH = "refresh"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token for authentication.
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token for obtaining new access tokens.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": TokenType.REFRESH})  # ✅ CHANGED
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise

# ============================================
# EMAIL VERIFICATION TOKENS
# ============================================

def create_verification_token(user_id: uuid.UUID, email: str) -> str:
    """
    Create email verification token.
    """
    expire_hours = int(os.getenv("VERIFICATION_TOKEN_EXPIRE_HOURS", "24"))
    expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    
    token_data = {
        "user_id": str(user_id),
        "email": email,
        "type": TokenType.EMAIL_VERIFICATION,  # ✅ CHANGED
        "exp": expire
    }
    
    return jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

def verify_verification_token(token: str) -> dict:
    """
    Verify and decode verification token.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify token type
        if payload.get("type") != TokenType.EMAIL_VERIFICATION:  # ✅ CHANGED
            raise JWTError("Invalid token type")
        
        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email")
        }
        
    except JWTError:
        raise

def create_password_reset_token(user_id: uuid.UUID, email: str) -> str:
    """
    Create password reset token.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    
    token_data = {
        "user_id": str(user_id),
        "email": email,
        "type": TokenType.PASSWORD_RESET,  # ✅ CHANGED
        "exp": expire
    }
    
    return jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

def verify_password_reset_token(token: str) -> dict:
    """
    Verify and decode password reset token.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify token type
        if payload.get("type") != TokenType.PASSWORD_RESET:  # ✅ CHANGED
            raise JWTError("Invalid token type")
        
        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email")
        }
        
    except JWTError:
        raise
