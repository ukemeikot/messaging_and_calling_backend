from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# 1. Get database URL (Check 'DATABASE_URL' for Render, 'DATABASE_URL_ASYNC' for local)
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_ASYNC")

# Validate DATABASE_URL exists
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL not found in environment variables. "
        "Please check your Render settings or .env file."
    )

# 2. Fix the protocol for AsyncPG (Render gives 'postgresql://', we need 'postgresql+asyncpg://')
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to False for production to reduce log noise
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