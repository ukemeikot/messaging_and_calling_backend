from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.api.v1 import auth, profile, contacts, chat  # Updated from 'chat' to 'messages'
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

app = FastAPI(
    title="Enterprise Messaging API",
    description="Production-ready messaging and calling API with OAuth",
    version="1.0.0", # Updated version
    docs_url="/docs",
    redoc_url="/redoc"
)

# Session middleware (required for OAuth)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-here"),
    max_age=3600,
    https_only=False,
    same_site="lax"
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
app.include_router(chat.router, prefix="/api/v1") # Points to /api/v1/messages

@app.get("/")
async def root():
    """API information and Quick Reference"""
    return {
        "message": "Welcome to Enterprise Messaging API",
        "version": "1.0.0",
        "docs": "/docs",
        "hybrid_architecture_notice": "Use REST for sending/editing/deleting. Use WebSocket for real-time delivery and events.",
        "endpoints": {
            "auth": {
                "register": "POST /api/v1/auth/register",
                "login": "POST /api/v1/auth/login"
            },
            "messaging": {
                "conversations": "GET /api/v1/messages/conversations",
                "create_dm": "POST /api/v1/messages/conversations",
                "create_group": "POST /api/v1/messages/conversations/group",
                "send_message": "POST /api/v1/messages",
                "history": "GET /api/v1/messages/conversations/{id}/messages",
                "websocket": "WS /api/v1/messages/ws?token={access_token}"
            }
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "enterprise-messaging-api",
        "environment": os.getenv("ENVIRONMENT", "development")
    }