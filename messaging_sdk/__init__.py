"""
Messaging & Calling SDK public package surface.

The package keeps imports intentionally light so utilities such as the CLI can
be executed before the full application configuration is available.
"""

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from messaging_sdk.emailing import EmailCustomization, configure_email_runtime


__version__ = "1.0.0"


class MessagingApp(FastAPI):
    """
    Main application class for the Messaging & Calling SDK.

    This class extends FastAPI and automatically configures:
    - Database connections
    - Authentication middleware
    - CORS settings
    - API routes
    - WebSocket endpoints
    - Static file serving
    """

    def __init__(
        self,
        settings: Any,
        email_customization: EmailCustomization | None = None,
        title: str = "Messaging & Calling API",
        description: str = "Production-ready messaging and calling API with OAuth",
        version: str = "1.0.0",
        **kwargs
        ):
        """
        Initialize the MessagingApp.

        Args:
            settings: Application configuration
            title: API title
            description: API description
            version: API version
            **kwargs: Additional FastAPI arguments
        """
        super().__init__(
            title=title,
            description=description,
            version=version,
            docs_url="/docs",
            redoc_url="/redoc",
            **kwargs
        )

        self.settings = settings
        self.email_customization = email_customization

        # Validate configuration
        issues = settings.validate_configuration()
        if issues:
            error_msg = "Configuration validation failed:\\n" + "\\n".join(f"  - {issue}" for issue in issues)
            raise ValueError(error_msg)

        # Configure the application
        configure_email_runtime(settings, email_customization)
        self._configure_middleware()
        self._configure_routes()
        self._configure_static_files()
        self._configure_database()

    def _configure_middleware(self):
        """Configure middleware (CORS, sessions, etc.)."""
        if "*" in self.settings.deployment.cors_origins and self.settings.deployment.environment != "development":
            raise ValueError("Wildcard CORS origins are only allowed in development")

        # Session middleware (required for OAuth)
        self.add_middleware(
            SessionMiddleware,
            secret_key=self.settings.security.secret_key,
            max_age=3600,
            https_only=False,
            same_site="lax"
        )

        # CORS middleware
        self.add_middleware(
            CORSMiddleware,
            allow_origins=self.settings.deployment.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _configure_routes(self):
        """Configure API routes."""
        from messaging_sdk.api.v1 import auth, profile, contacts, chat, search, calls
        from messaging_sdk.api.v1 import websocket_signaling

        # Include API routers
        self.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
        self.include_router(profile.router, prefix="/api/v1", tags=["Profile"])
        self.include_router(contacts.router, prefix="/api/v1", tags=["Contacts"])
        self.include_router(chat.router, prefix="/api/v1", tags=["Messaging"])
        self.include_router(search.router, prefix="/api/v1", tags=["Search"])
        self.include_router(calls.router, prefix="/api/v1", tags=["Calls"])

        # Register WebSocket router
        self.include_router(websocket_signaling.router, prefix="/api/v1", tags=["WebRTC"])

    def _configure_static_files(self):
        """Configure static file serving."""
        # Create uploads directory if it doesn't exist
        uploads_dir = Path("uploads")
        uploads_dir.mkdir(exist_ok=True)
        (uploads_dir / "profile_pictures").mkdir(exist_ok=True)

        # Mount static files
        self.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    def _configure_database(self):
        """Configure database connection and create tables."""
        self.add_event_handler("startup", self._create_tables)

    async def _create_tables(self):
        """Create database tables."""
        from messaging_sdk.database import engine, Base

        try:
            async with engine.begin() as conn:
                # Create all tables
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            print(f"Warning: Could not create database tables: {e}")
            print("You may need to run migrations manually.")

    async def startup_event(self):
        """Application startup event."""
        # Additional startup logic can be added here
        pass

    async def shutdown_event(self):
        """Application shutdown event."""
        # Additional shutdown logic can be added here
        pass


# Export key components for easy importing
__all__ = [
    "MessagingApp",
    "EmailCustomization",
    "__version__",
]


def __getattr__(name: str):
    """Provide backward-compatible lazy exports."""
    if name == "Settings":
        from messaging_sdk.core.config import Settings

        return Settings
    if name == "get_db":
        from messaging_sdk.database import get_db

        return get_db
    if name == "EmailTheme":
        from messaging_sdk.emailing import EmailTheme

        return EmailTheme
    raise AttributeError(f"module 'messaging_sdk' has no attribute {name!r}")
