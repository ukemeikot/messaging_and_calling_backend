from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment with type checking
DATABASE_URL = os.getenv("DATABASE_URL_ASYNC")

# Validate DATABASE_URL exists
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL_ASYNC not found in environment variables. "
        "Please check your .env file."
    )

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Shows SQL queries in console (set False in production)
    future=True,
    pool_pre_ping=True,  # Checks connection before using
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