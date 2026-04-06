"""added_new_chat_features

Revision ID: e0b3502e9308
Revises: v1_hybrid_base
Create Date: 2025-12-20 17:10:36.976284

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e0b3502e9308'
down_revision: Union[str, Sequence[str], None] = 'v1_hybrid_base'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # 1. Handle 'conversations' table
    # Add column as nullable first to avoid immediate crash
    op.add_column('conversations', sa.Column('admin_only_add_members', sa.Boolean(), nullable=True))
    
    # Set a default value for existing rows
    op.execute("UPDATE conversations SET admin_only_add_members = False")
    
    # Now enforce NOT NULL
    op.alter_column('conversations', 'admin_only_add_members', nullable=False)

    # 2. Handle 'messages' table columns
    # Ensure no NULLs exist in is_edited before making it non-nullable
    op.execute("UPDATE messages SET is_edited = False WHERE is_edited IS NULL")
    op.alter_column('messages', 'is_edited',
               existing_type=sa.BOOLEAN(),
               nullable=False)

    # Ensure no NULLs exist in is_deleted before making it non-nullable
    op.execute("UPDATE messages SET is_deleted = False WHERE is_deleted IS NULL")
    op.alter_column('messages', 'is_deleted',
               existing_type=sa.BOOLEAN(),
               nullable=False)

    # Safely drop the old is_read column as per your previous design update
    op.drop_column('messages', 'is_read')


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add is_read column
    op.add_column('messages', sa.Column('is_read', sa.Boolean(), nullable=True))
    op.execute("UPDATE messages SET is_read = False")
    op.alter_column('messages', 'is_read', nullable=False)

    # Revert NOT NULL constraints
    op.alter_column('messages', 'is_deleted',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('messages', 'is_edited',
               existing_type=sa.BOOLEAN(),
               nullable=True)
               
    # Remove the new group feature column
    op.drop_column('conversations', 'admin_only_add_members')