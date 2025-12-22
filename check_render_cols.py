import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def check():
    engine = create_async_engine(URL)
    async with engine.connect() as conn:
        # Check if the NEW column exists in conversations
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='conversations' AND column_name='admin_only_add_members';
        """))
        column = result.scalar()
        
        if column:
            print("✅ CONFIRMED: 'admin_only_add_members' exists on Render!")
        else:
            print("❌ NOT FOUND: The column is missing on Render.")

        # Check if the OLD column is gone from messages
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='messages' AND column_name='is_read';
        """))
        old_col = result.scalar()
        
        if not old_col:
            print("✅ CONFIRMED: Old 'is_read' column was successfully dropped from Render!")
        else:
            print("❌ WARNING: 'is_read' still exists on Render.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())