import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# YOUR RENDER URL
DATABASE_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def fix():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        print("Adding missing 'is_online' column...")
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_online BOOLEAN DEFAULT FALSE;"))
        
        # Also ensure 'last_seen' exists if your SearchService uses it
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP WITH TIME ZONE;"))
        
    print("✅ Database columns synchronized with Model!")

if __name__ == "__main__":
    asyncio.run(fix())