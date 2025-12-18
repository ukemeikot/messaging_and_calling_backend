from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.api.v1 import auth, profile, contacts, chat
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

app = FastAPI(
    title="Enterprise Messaging API",
    description="Production-ready messaging and calling API with OAuth",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Session middleware (required for OAuth)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-here"),
    max_age=3600,       # Session expires in 1 hour
    https_only=False,   # <--- ESSENTIAL for local development (allows HTTP)
    same_site="lax"     # <--- Allows cookies during redirects
)

# CORS middleware
CORS_ORIGINS = eval(os.getenv("CORS_ORIGINS", '["*"]'))

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory
Path("uploads/profile_pictures").mkdir(parents=True, exist_ok=True)

# Serve static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")

@app.get("/")
async def root():
    """API information"""
    return {
        "message": "Welcome to Enterprise Messaging API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "auth": {
                "register": "POST /api/v1/auth/register",
                "login": "POST /api/v1/auth/login",
                "me": "GET /api/v1/auth/me"
            },
            "contacts": {
                "search": "GET /api/v1/contacts/search",
                "list": "GET /api/v1/contacts",
                "request": "POST /api/v1/contacts/request",
                "pending": "GET /api/v1/contacts/pending"
            },
            "chat": {
                "websocket": "WS /api/v1/chat/ws?token={access_token}",
                "start_dm": "POST /api/v1/chat/conversations/direct",
                "create_group": "POST /api/v1/chat/conversations/group",
                "list_conversations": "GET /api/v1/chat/conversations",
                "history": "GET /api/v1/chat/conversations/{id}/messages"
            }
        }
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "service": "enterprise-messaging-api",
        "version": "0.1.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "debug": os.getenv("DEBUG", "True")
    }