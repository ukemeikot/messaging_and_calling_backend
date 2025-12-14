from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Enterprise Messaging API",
    description="Production-ready messaging and calling API with authentication",
    version="0.1.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc alternative
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

# Include routers
app.include_router(auth.router, prefix="/api/v1")

@app.get("/")
async def root():
    """
    Root endpoint - API information
    """
    return {
        "message": "Welcome to Enterprise Messaging API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "register": "POST /api/v1/auth/register",
            "login": "POST /api/v1/auth/login (coming soon)",
            "health": "GET /health"
        }
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint - for monitoring
    """
    return {
        "status": "healthy",
        "service": "enterprise-messaging-api",
        "version": "0.1.0"
    }