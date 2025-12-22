import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Your Render Database URL
DATABASE_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def fix_table():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        print("🔌 Connecting to Render DB...")
        
        print("🛠 Fixing 'conversation_participants' table...")
        try:
            # This sets the default value for the 'id' column to a random UUID
            await conn.execute(text((
                "ALTER TABLE conversation_participants "
                "ALTER COLUMN id SET DEFAULT gen_random_uuid();"
            )))
            # We also do the same for 'messages' table just in case!
            await conn.execute(text((
                "ALTER TABLE messages "
                "ALTER COLUMN id SET DEFAULT gen_random_uuid();"
            )))
            
            await conn.commit()
            print("✅ Success! ID columns will now auto-generate.")
        except Exception as e:
            print(f"❌ Error: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_table())