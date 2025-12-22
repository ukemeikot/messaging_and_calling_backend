import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Your Render Database URL
DATABASE_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

async def fix_enum():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        print("🔌 Connecting to Render DB...")
        
        # 1. Create the missing ENUM type
        print("🛠 Creating Type 'contact_status'...")
        try:
            # We use distinct values. Ensure these match your Python Enum exactly!
            await conn.execute(text("CREATE TYPE contact_status AS ENUM ('PENDING', 'ACCEPTED', 'BLOCKED');"))
            print("✅ Type created successfully.")
        except Exception as e:
            if "already exists" in str(e):
                print("⚠️ Type already exists (that's okay).")
            else:
                print(f"❌ Error creating type: {e}")

        # 2. ALTER the table to use this new type
        # (This forces the 'status' column to stop being a String and start being an Enum)
        print("🔄 Converting column 'status' to use the new Type...")
        try:
            await conn.execute(text((
                "ALTER TABLE contacts "
                "ALTER COLUMN status TYPE contact_status "
                "USING status::contact_status;"
            )))
            print("✅ Column converted successfully.")
        except Exception as e:
             print(f"❌ Error converting column: {e}")
             print("(If the table is empty, this error might be fine. The Type creation is the important part.)")

        await conn.commit()
        print("🚀 Done! You can now send requests.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_enum())