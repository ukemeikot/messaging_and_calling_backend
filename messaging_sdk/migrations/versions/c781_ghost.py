"""ghost migration
Revision ID: c781b3435f7e
Revises: None
Create Date: 2025-12-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'c781b3435f7e'
down_revision = None # We set this to None to break the dependency on older missing files
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass