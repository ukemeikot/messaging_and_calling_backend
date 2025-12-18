import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Your Render Database URL
DATABASE_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def check_tables():
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.connect() as conn:
            print("\nConnecting to Render Database...")
            result = await conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            ))
            tables = result.fetchall()
            
            print("\n--- CURRENT TABLES ---")
            found_contacts = False
            if not tables:
                print("No tables found! (Database is empty)")
            for table in tables:
                print(f"✅ {table[0]}")
                if table[0] == 'contacts':
                    found_contacts = True
            
            print("----------------------")
            if not found_contacts:
                print("❌ ERROR: 'contacts' table is MISSING.")
            else:
                print("✅ SUCCESS: 'contacts' table EXISTS.")
                
        await engine.dispose()
    except Exception as e:
        print(f"\n❌ CONNECTION FAILED: {str(e)}")
        print("Tip: Go to Render Dashboard -> Postgres -> Access Control -> Add Current IP")

if __name__ == "__main__":
    asyncio.run(check_tables())