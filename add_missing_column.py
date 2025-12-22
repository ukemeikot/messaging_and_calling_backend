import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Your Render Database URL
DATABASE_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def add_column():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        print("🔌 Connecting to Render DB...")
        
        print("🛠 Adding missing column 'description' to 'conversations'...")
        try:
            # We add it as nullable (optional) so it doesn't break existing rows
            await conn.execute(text("ALTER TABLE conversations ADD COLUMN description VARCHAR(500);"))
            await conn.commit()
            print("✅ Success! Column 'description' added.")
        except Exception as e:
            if "already exists" in str(e):
                print("⚠️ Column already exists (skipping).")
            else:
                print(f"❌ Error adding column: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(add_column())