from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.api.v1 import auth, profile
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
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-here")
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
                "google_login": "GET /api/v1/auth/google/login",
                "me": "GET /api/v1/auth/me"
            },
            "profile": {
                "get": "GET /api/v1/profile",
                "update": "PUT /api/v1/profile",
                "change_password": "POST /api/v1/profile/password",
                "upload_picture": "POST /api/v1/profile/picture",
                "view_user": "GET /api/v1/profile/{user_id}"
            }
        }
    }

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "enterprise-messaging-api",
        "version": "0.1.0"
    }