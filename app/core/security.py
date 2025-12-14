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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token for authentication.
    
    Args:
        data: Dictionary containing user information (user_id, username, etc.)
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
        
    Example:
        token = create_access_token({"user_id": 1, "username": "ukeme"})
        # Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        
    Security:
        - Short-lived (15 minutes by default)
        - Signed with SECRET_KEY (can't be tampered with)
        - Contains expiration time (exp claim)
        
    Why timezone-aware?
        - Prevents timezone bugs (server in US, user in Nigeria)
        - JWT standard requires UTC timestamps
        - Python 3.12+ deprecates naive datetime
    """
    to_encode = data.copy()
    
    # Set expiration time (timezone-aware UTC)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add expiration to token payload
    to_encode.update({"exp": expire})
    
    # Encode and return token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token for obtaining new access tokens.
    
    Args:
        data: Dictionary containing user information
        
    Returns:
        Encoded JWT refresh token string
        
    Security:
        - Long-lived (7 days by default)
        - Used to get new access tokens without re-login
        - Should be stored securely on client (HttpOnly cookie preferred)
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary containing token payload
        
    Raises:
        JWTError: If token is invalid, expired, or tampered with
        
    Security:
        - Verifies token signature (detects tampering)
        - Checks expiration time (rejects expired tokens)
        - Validates token structure
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise