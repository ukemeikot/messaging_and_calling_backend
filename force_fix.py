import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# 1. PASTE YOUR RENDER DB URL HERE
DATABASE_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

# 2. PASTE THE ID FROM YOUR UUID FILE HERE (Keep the quotes!)
# Example: GOOD_REVISION_ID = "1a2b3c4d5e6f"
GOOD_REVISION_ID = "191b01c2f720"

async def force_fix():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        print(f"🔌 Connecting to database...")
        
        # Verify connection
        await conn.execute(text("SELECT 1"))
        print(f"✅ Connected.")

        print(f"🔨 Forcing database version to: {GOOD_REVISION_ID}")
        
        # 1. Clear the current (bad) version
        await conn.execute(text("DELETE FROM alembic_version"))
        
        # 2. Insert the good version
        await conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{GOOD_REVISION_ID}')"))
        
        await conn.commit()
        print("✅ SUCCESS: Database version updated manually.")
        print("🚀 You can now run 'alembic upgrade head'")

    await engine.dispose()

if __name__ == "__main__":
    if GOOD_REVISION_ID == "PASTE_YOUR_UUID_REV_ID_HERE":
        print("❌ ERROR: You forgot to paste your Revision ID in the script!")
    else:
        asyncio.run(force_fix())