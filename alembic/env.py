from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import your Base and models
from app.database import Base
# Ensure all models are imported so Alembic can see them for autogenerate
from app.models import User, Contact, Conversation, Message 

# Alembic Config object
config = context.config

# --- RESTORED DYNAMIC URL LOGIC ---
# This pulls the URL from your environment variables (Local or Render)
DATABASE_URL = os.getenv("DATABASE_URL_ASYNC")

if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
# ----------------------------------

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async."""
    # We create the configuration for the engine
    section = config.get_section(config.config_ini_section)
    if section is None:
        raise ValueError("Could not get alembic configuration section")
        
    configuration = dict(section)
    
    # Ensure the engine uses the environment-provided URL
    if DATABASE_URL:
        configuration["sqlalchemy.url"] = DATABASE_URL
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()