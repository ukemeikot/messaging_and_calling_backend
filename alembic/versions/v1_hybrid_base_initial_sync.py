"""initial_sync

Revision ID: v1_hybrid_base
Revises: v2025_hybrid_base
Create Date: 2025-12-20 16:15:35.303965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v1_hybrid_base'
down_revision: Union[str, Sequence[str], None] = 'v2025_hybrid_base'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
