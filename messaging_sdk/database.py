"""
Database configuration for Messaging & Calling SDK.

This module provides database connection management using SQLAlchemy async.
Supports PostgreSQL and SQLite for testing.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.types import TypeDecorator
from sqlalchemy import String

from messaging_sdk.core.config import settings


class SearchVector(TypeDecorator):
    """Fallback search vector type for SQLite compatibility."""
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import TSVECTOR
            return dialect.type_descriptor(TSVECTOR())
        return dialect.type_descriptor(String())

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value


class JSONType(TypeDecorator):
    """Fallback JSON type for cross-dialect compatibility."""
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        from sqlalchemy import JSON
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value


# Get database URL from settings (already validated and protocol-fixed)
DATABASE_URL = settings.database_url

# Create async engine with appropriate driver
if DATABASE_URL.startswith("sqlite"):
    # SQLite for testing
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.deployment.debug,
        future=True,
        pool_pre_ping=False,  # Not needed for SQLite
        connect_args={"check_same_thread": False},  # Needed for SQLite async
    )
else:
    # PostgreSQL for production
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.deployment.debug,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Create declarative base for models
Base = declarative_base()

# Dependency to get database session
async def get_db():
    """
    Database session dependency for FastAPI routes.
    Usage: async def my_route(db: AsyncSession = Depends(get_db))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()