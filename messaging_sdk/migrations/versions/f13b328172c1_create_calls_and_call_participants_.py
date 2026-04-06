"""
Create calls and call_participants tables with group call support

Revision ID: create_calls_tables
Revises: add_search_indexes
Create Date: 2024-12-23 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_calls_tables'
down_revision = '0733151471c5'
branch_label = None
depends_on = None


def upgrade() -> None:
    # --- CRITICAL FIX: Ensure UUID extension exists ---
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    # ============================================
    # CALLS TABLE
    # ============================================
    op.create_table(
        'calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('initiator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('call_type', sa.String(20), nullable=False),  # 'audio' or 'video'
        sa.Column('call_mode', sa.String(20), nullable=False),  # '1-on-1' or 'group'
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('max_participants', sa.Integer, nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer, nullable=True),
        sa.Column('ended_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('end_reason', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        
        sa.ForeignKeyConstraint(['initiator_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ended_by'], ['users.id'], ondelete='SET NULL'),
        
        sa.CheckConstraint("call_type IN ('audio', 'video')", name='calls_call_type_check'),
        sa.CheckConstraint("call_mode IN ('1-on-1', 'group')", name='calls_call_mode_check'),
        sa.CheckConstraint("status IN ('ringing', 'active', 'ended', 'missed', 'declined', 'failed', 'cancelled')", name='calls_status_check'),
        sa.CheckConstraint("max_participants IS NULL OR max_participants >= 2", name='calls_max_participants_check')
    )
    
    op.create_index('idx_calls_initiator_id', 'calls', ['initiator_id'])
    op.create_index('idx_calls_status', 'calls', ['status'])
    op.create_index('idx_calls_call_mode', 'calls', ['call_mode'])
    op.create_index('idx_calls_started_at', 'calls', ['started_at'])
    
    # ============================================
    # CALL PARTICIPANTS TABLE
    # ============================================
    op.create_table(
        'call_participants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('invited_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_muted', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_video_enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('is_screen_sharing', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('connection_quality', sa.String(20), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        
        sa.ForeignKeyConstraint(['call_id'], ['calls.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint("role IN ('initiator', 'participant')", name='call_participants_role_check'),
        sa.CheckConstraint("status IN ('ringing', 'joined', 'left', 'declined', 'missed')", name='call_participants_status_check'),
        sa.UniqueConstraint('call_id', 'user_id', name='uq_call_participants_call_user')
    )
    
    op.create_index('idx_call_participants_call_id', 'call_participants', ['call_id'])
    op.create_index('idx_call_participants_user_id', 'call_participants', ['user_id'])
    
    # ============================================
    # CALL INVITATIONS TABLE
    # ============================================
    op.create_table(
        'call_invitations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invited_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('invited_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        
        sa.ForeignKeyConstraint(['call_id'], ['calls.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'declined', 'expired')", name='call_invitations_status_check'),
        sa.UniqueConstraint('call_id', 'invited_user_id', name='uq_call_invitations_call_user')
    )

    # ============================================
    # TRIGGERS & FUNCTIONS
    # ============================================
    
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("CREATE TRIGGER calls_updated_at_trigger BEFORE UPDATE ON calls FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();")
    op.execute("CREATE TRIGGER call_participants_updated_at_trigger BEFORE UPDATE ON call_participants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();")
    
    op.execute("""
        CREATE OR REPLACE FUNCTION calculate_call_duration()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.ended_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
                NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.ended_at - NEW.started_at))::INTEGER;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("CREATE TRIGGER calls_duration_trigger BEFORE UPDATE ON calls FOR EACH ROW EXECUTE FUNCTION calculate_call_duration();")
    
    op.execute("""
        CREATE OR REPLACE FUNCTION update_call_status_on_participant_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.status = 'joined' THEN
                UPDATE calls SET status = 'active' WHERE id = NEW.call_id AND status = 'ringing';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("CREATE TRIGGER participant_status_update_trigger AFTER UPDATE ON call_participants FOR EACH ROW EXECUTE FUNCTION update_call_status_on_participant_change();")


def downgrade() -> None:
    op.drop_table('call_invitations')
    op.drop_table('call_participants')
    op.drop_table('calls')
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;')
    op.execute('DROP FUNCTION IF EXISTS calculate_call_duration() CASCADE;')
    op.execute('DROP FUNCTION IF EXISTS update_call_status_on_participant_change() CASCADE;')