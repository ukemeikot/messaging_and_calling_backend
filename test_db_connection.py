import asyncio
import asyncpg

async def test_connection():
    print("🔄 Attempting to connect to PostgreSQL...")
    print("📍 Host: localhost")
    print("👤 User: enterprise_user")
    print("🗄️  Database: enterprise_messaging_db")
    print("")
    
    try:
        conn = await asyncpg.connect(
            user='fastapi',
            password='SecurePass123!',
            database='enterprise_messaging_db',
            host='localhost',
            port=5432
        )
        
        version = await conn.fetchval('SELECT version()')
        
        print("=" * 60)
        print("✅ SUCCESS! Python connected to PostgreSQL")
        print("=" * 60)
        print(f"📊 Database version:")
        print(f"   {version[:80]}...")
        print("")
        print("🎉 Your database is ready for the FastAPI app!")
        print("=" * 60)
        
        await conn.close()
        
    except Exception as e:
        print("=" * 60)
        print("❌ ERROR: Could not connect to PostgreSQL")
        print("=" * 60)
        print(f"Error details: {e}")
        print("")
        print("Troubleshooting:")
        print("1. Is PostgreSQL running? (Check Postgres.app or pgAdmin)")
        print("2. Is the password correct? (SecurePass123!)")
        print("3. Did you create the database? (Run Part 4 again)")
        print("=" * 60)

asyncio.run(test_connection())