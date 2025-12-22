import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def sync():
    engine = create_async_engine(URL)
    async with engine.begin() as conn:
        print("🚀 Syncing Render Schema...")
        
        # 1. Ensure Enum exists
        await conn.execute(text("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_type') THEN CREATE TYPE message_type AS ENUM ('text', 'image', 'video', 'audio', 'file', 'system'); END IF; END $$;"))

        # 2. Add all missing columns we discussed
        await conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS description VARCHAR(500), ADD COLUMN IF NOT EXISTS last_message TEXT, ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMP WITH TIME ZONE"))
        await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_edited BOOLEAN DEFAULT FALSE, ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP WITH TIME ZONE, ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE, ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE"))
        await conn.execute(text("ALTER TABLE conversation_participants ADD COLUMN IF NOT EXISTS last_read_message_id UUID, ADD COLUMN IF NOT EXISTS last_read_at TIMESTAMP WITH TIME ZONE"))

        # 3. Clean up timestamps and set NOT NULL
        await conn.execute(text("UPDATE conversations SET updated_at = NOW() WHERE updated_at IS NULL"))
        await conn.execute(text("ALTER TABLE conversations ALTER COLUMN updated_at SET NOT NULL"))

        # 4. RESET ALEMBIC HISTORY
        print("💾 Stamping database with version: 'v2025_base'")
        await conn.execute(text("DELETE FROM alembic_version"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('v2025_base')"))

    print("✅ Render Database is now synchronized!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(sync())