import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Your Render URL
DATABASE_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def test_insert():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        print("🔌 Connecting to Render DB...")
        
        # 1. Check if table exists
        print("🔍 Checking schema...")
        await conn.execute(text("SELECT id FROM contacts LIMIT 1"))
        print("✅ Table 'contacts' exists and is readable.")

        # 2. Try to insert a dummy row (Raw SQL to bypass model issues)
        # We use random UUIDs for user_ids just to see if the TABLE accepts the insert
        # Note: This might fail on Foreign Key constraint if users don't exist, 
        # but that proves the table IS there.
        print("📝 Attempting raw insert...")
        try:
            # We select a real user ID first to avoid Foreign Key errors
            result = await conn.execute(text("SELECT id FROM users LIMIT 1"))
            user = result.fetchone()
            
            if user:
                uid = user[0]
                await conn.execute(text(f"""
                    INSERT INTO contacts (id, user_id, contact_user_id, status, created_at)
                    VALUES ('{uuid.uuid4()}', '{uid}', '{uid}', 'pending', now())
                """))
                print("✅ INSERT SUCCESSFUL! The database is fully working.")
                await conn.rollback() # Undo the test insert
            else:
                print("⚠️ Cannot test insert: No users found in DB (but table check passed).")
                
        except Exception as e:
            if "violates foreign key constraint" in str(e):
                 print("✅ Table exists! (Got foreign key error, which means the table is there).")
            else:
                print(f"❌ Insert Failed: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_insert())