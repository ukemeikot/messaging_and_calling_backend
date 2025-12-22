import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def stamp():
    engine = create_async_engine(URL)
    async with engine.begin() as conn:
        print("Stamping database...")
        await conn.execute(text("DELETE FROM alembic_version"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('v1_hybrid_base')"))
    print("✅ Database stamped as v1_hybrid_base")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(stamp())