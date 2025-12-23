import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Use the ASYNC version of your Render URL
RENDER_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def verify():
    engine = create_async_engine(RENDER_URL)
    print(f"Connecting to: {RENDER_URL.split('@')[-1]}...")
    
    try:
        async with engine.connect() as conn:
            # 1. Check current database name
            db_name = await conn.scalar(text("SELECT current_database()"))
            print(f"✅ Connected to Database: {db_name}")

            # 2. List all tables
            result = await conn.execute(text(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
            ))
            tables = [row[0] for row in result.all()]
            
            print(f"✅ Tables found in 'public' schema: {tables}")
            
            expected = ['calls', 'call_participants', 'call_invitations']
            missing = [t for t in expected if t not in tables]
            
            if not missing:
                print("🚀 SUCCESS: All calling tables exist!")
            else:
                print(f"❌ MISSING TABLES: {missing}")
                print("💡 Tip: Your Alembic migration might have been recorded as 'done' in 'alembic_version' but the tables weren't actually committed.")

    except Exception as e:
        print(f"❌ Connection Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify())