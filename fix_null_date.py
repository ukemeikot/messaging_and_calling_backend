import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Your Render Database URL
DATABASE_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def fix_all_null_dates():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        print("🔌 Connecting to Render Database...")
        
        try:
            # Fix Conversations
            print("📅 Fixing Conversations...")
            await conn.execute(text("UPDATE conversations SET updated_at = now() WHERE updated_at IS NULL;"))
            
            # Fix Contacts
            print("📅 Fixing Contacts...")
            await conn.execute(text("UPDATE contacts SET updated_at = now() WHERE updated_at IS NULL;"))
            
            # Fix Messages
            print("📅 Fixing Messages...")
            await conn.execute(text("UPDATE messages SET updated_at = now() WHERE updated_at IS NULL;"))
            
            await conn.commit()
            print("✅ SUCCESS: All NULL dates have been filled with current timestamps.")
            print("🚀 Try your request in Swagger now!")
            
        except Exception as e:
            print(f"❌ Error: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_all_null_dates())