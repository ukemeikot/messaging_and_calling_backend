import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# YOUR RENDER URL
RENDER_URL = "postgresql+asyncpg://enterprise_user:X7C2e7ztq3ZpkvXVfJQSBovVDQVGlQOH@dpg-d51sbklactks73a867lg-a.virginia-postgres.render.com/enterprise_messaging_db"

SQL_COMMANDS = [
    'CREATE EXTENSION IF NOT EXISTS "pgcrypto";',
    
    # 1. Create Calls Table
    """
    CREATE TABLE IF NOT EXISTS calls (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        initiator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        call_type VARCHAR(20) NOT NULL,
        call_mode VARCHAR(20) NOT NULL,
        status VARCHAR(20) NOT NULL,
        max_participants INTEGER,
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        ended_at TIMESTAMPTZ,
        duration_seconds INTEGER,
        ended_by UUID REFERENCES users(id) ON DELETE SET NULL,
        end_reason VARCHAR(50),
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,

    # 2. Create Call Participants
    """
    CREATE TABLE IF NOT EXISTS call_participants (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role VARCHAR(20) NOT NULL,
        status VARCHAR(20) NOT NULL,
        invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        joined_at TIMESTAMPTZ,
        left_at TIMESTAMPTZ,
        is_muted BOOLEAN NOT NULL DEFAULT FALSE,
        is_video_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        is_screen_sharing BOOLEAN NOT NULL DEFAULT FALSE,
        connection_quality VARCHAR(20),
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(call_id, user_id)
    );
    """,

    # 3. Create Call Invitations
    """
    CREATE TABLE IF NOT EXISTS call_invitations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
        invited_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        invited_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        status VARCHAR(20) NOT NULL,
        invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        responded_at TIMESTAMPTZ,
        expires_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(call_id, invited_user_id)
    );
    """,

    # 4. Triggers
    """
    CREATE OR REPLACE FUNCTION update_call_status_on_participant_change()
    RETURNS TRIGGER AS $$
    BEGIN
        IF NEW.status = 'joined' THEN
            UPDATE calls SET status = 'active' WHERE id = NEW.call_id AND status = 'ringing';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,
    
    "DROP TRIGGER IF EXISTS participant_status_update_trigger ON call_participants;",
    
    """
    CREATE TRIGGER participant_status_update_trigger
    AFTER UPDATE ON call_participants
    FOR EACH ROW EXECUTE FUNCTION update_call_status_on_participant_change();
    """
]

async def run_force_creation():
    engine = create_async_engine(RENDER_URL)
    print("🚀 Connecting to Render to force create tables...")
    
    async with engine.begin() as conn:
        for cmd in SQL_COMMANDS:
            try:
                await conn.execute(text(cmd))
                print(f"✅ Executed successfully.")
            except Exception as e:
                print(f"⚠️ Error executing command: {e}")
    
    print("\n🏁 Process finished. Check your verify_db.py script now!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_force_creation())