"""manual_create_contacts_and_chat

Revision ID: manual_force_001
Revises: <KEEP_YOUR_PREVIOUS_REVISION_ID_HERE>
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'manual_force_001'
down_revision = '191b01c2f720'  # <--- IMPORTANT: CHECK BELOW

def upgrade() -> None:
    # --- 1. Create CONTACTS Table ---
    op.create_table('contacts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('contact_user_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['contact_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # --- 2. Create CONVERSATIONS Table ---
    op.create_table('conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('is_group', sa.Boolean(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('group_image_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # --- 3. Create PARTICIPANTS Table ---
    op.create_table('conversation_participants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # --- 4. Create MESSAGES Table ---
    op.create_table('messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('sender_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_type', sa.Enum('TEXT', 'IMAGE', 'VIDEO', 'AUDIO', 'FILE', 'SYSTEM', name='messagetype'), nullable=False),
        sa.Column('media_url', sa.String(length=500), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('reply_to_message_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.ForeignKeyConstraint(['reply_to_message_id'], ['messages.id'], ),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('messages')
    op.drop_table('conversation_participants')
    op.drop_table('conversations')
    op.drop_table('contacts')
    # Drop Enum type if needed
    op.execute("DROP TYPE messagetype")