"""add search indexes

Revision ID: 0733151471c5
Revises: e0b3502e9308
Create Date: 2025-12-23 10:02:46.635259

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0733151471c5'
down_revision: Union[str, Sequence[str], None] = ('c781b3435f7e', 'e0b3502e9308')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add search capabilities:
    1. Enable PostgreSQL extensions (pg_trgm for fuzzy search)
    2. Add GIN indexes for fast text search
    3. Add tsvector columns for full-text search
    """
    
    # Enable PostgreSQL extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')
    op.execute('CREATE EXTENSION IF NOT EXISTS unaccent;')
    
    # ============================================
    # USERS TABLE - Search Indexes
    # ============================================
    
    # Add search_vector column for full-text search
    op.add_column(
        'users',
        sa.Column('search_vector', postgresql.TSVECTOR, nullable=True)
    )
    
    # Create GIN indexes for trigram similarity search (fuzzy matching)
    op.execute("""
        CREATE INDEX idx_users_username_trgm 
        ON users USING gin(username gin_trgm_ops);
    """)
    
    op.execute("""
        CREATE INDEX idx_users_full_name_trgm 
        ON users USING gin(full_name gin_trgm_ops);
    """)
    
    op.execute("""
        CREATE INDEX idx_users_email_trgm 
        ON users USING gin(email gin_trgm_ops);
    """)
    
    # Create GIN index for full-text search
    op.execute("""
        CREATE INDEX idx_users_search_vector 
        ON users USING gin(search_vector);
    """)
    
    # Create trigger to automatically update search_vector
    op.execute("""
        CREATE OR REPLACE FUNCTION users_search_vector_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.username, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.full_name, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.email, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER users_search_vector_update 
        BEFORE INSERT OR UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION users_search_vector_trigger();
    """)
    
    # Update existing rows
    op.execute("""
        UPDATE users SET search_vector = 
            setweight(to_tsvector('english', coalesce(username, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(full_name, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(email, '')), 'C');
    """)
    
    # ============================================
    # MESSAGES TABLE - Search Indexes
    # ============================================
    
    op.add_column(
        'messages',
        sa.Column('search_vector', postgresql.TSVECTOR, nullable=True)
    )
    
    op.execute("CREATE INDEX idx_messages_content_trgm ON messages USING gin(content gin_trgm_ops);")
    op.execute("CREATE INDEX idx_messages_search_vector ON messages USING gin(search_vector);")
    
    op.execute("""
        CREATE OR REPLACE FUNCTION messages_search_vector_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', coalesce(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER messages_search_vector_update 
        BEFORE INSERT OR UPDATE ON messages
        FOR EACH ROW EXECUTE FUNCTION messages_search_vector_trigger();
    """)
    
    op.execute("UPDATE messages SET search_vector = to_tsvector('english', coalesce(content, ''));")

    # ============================================
    # CONVERSATIONS TABLE - Search Indexes
    # ============================================
    
    op.add_column(
        'conversations',
        sa.Column('search_vector', postgresql.TSVECTOR, nullable=True)
    )
    
    op.execute("CREATE INDEX idx_conversations_name_trgm ON conversations USING gin(name gin_trgm_ops);")
    op.execute("CREATE INDEX idx_conversations_search_vector ON conversations USING gin(search_vector);")
    
    op.execute("""
        CREATE OR REPLACE FUNCTION conversations_search_vector_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', coalesce(NEW.name, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER conversations_search_vector_update 
        BEFORE INSERT OR UPDATE ON conversations
        FOR EACH ROW EXECUTE FUNCTION conversations_search_vector_trigger();
    """)
    
    op.execute("UPDATE conversations SET search_vector = to_tsvector('english', coalesce(name, ''));")

    # ============================================
    # Additional Performance Indexes
    # ============================================
    
    op.create_index('idx_users_is_online', 'users', ['is_online'], postgresql_where=sa.text('is_online = true'))
    op.create_index('idx_users_is_verified', 'users', ['is_verified'], postgresql_where=sa.text('is_verified = true'))
    op.create_index('idx_messages_conversation_created', 'messages', ['conversation_id', 'created_at'])


def downgrade() -> None:
    """Remove search indexes and extensions"""
    
    op.drop_index('idx_users_username_trgm', table_name='users')
    op.drop_index('idx_users_full_name_trgm', table_name='users')
    op.drop_index('idx_users_email_trgm', table_name='users')
    op.drop_index('idx_users_search_vector', table_name='users')
    op.drop_index('idx_users_is_online', table_name='users')
    op.drop_index('idx_users_is_verified', table_name='users')
    
    op.drop_index('idx_messages_content_trgm', table_name='messages')
    op.drop_index('idx_messages_search_vector', table_name='messages')
    op.drop_index('idx_messages_conversation_created', table_name='messages')
    
    op.drop_index('idx_conversations_name_trgm', table_name='conversations')
    op.drop_index('idx_conversations_search_vector', table_name='conversations')
    
    op.execute('DROP TRIGGER IF EXISTS users_search_vector_update ON users;')
    op.execute('DROP TRIGGER IF EXISTS messages_search_vector_update ON messages;')
    op.execute('DROP TRIGGER IF EXISTS conversations_search_vector_update ON conversations;')
    
    op.execute('DROP FUNCTION IF EXISTS users_search_vector_trigger();')
    op.execute('DROP FUNCTION IF EXISTS messages_search_vector_trigger();')
    op.execute('DROP FUNCTION IF EXISTS conversations_search_vector_trigger();')
    
    op.drop_column('users', 'search_vector')
    op.drop_column('messages', 'search_vector')
    op.drop_column('conversations', 'search_vector')