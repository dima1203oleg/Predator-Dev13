"""Add IndexError table for DLQ

Revision ID: add_index_errors_dlq
Revises:
Create Date: 2025-01-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_index_errors_dlq'
down_revision = None  # Replace with actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    # Create index_errors table
    op.create_table(
        'index_errors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_db', sa.String(length=50), nullable=False),
        sa.Column('operation', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('error_type', sa.String(length=100), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=True, server_default='3'),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='pending'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payload_snapshot', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['record_id'], ['records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_index_error_record', 'index_errors', ['record_id'], unique=False)
    op.create_index('idx_index_error_target', 'index_errors', ['target_db'], unique=False)
    op.create_index('idx_index_error_status', 'index_errors', ['status'], unique=False)
    op.create_index('idx_index_error_created', 'index_errors', ['created_at'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index('idx_index_error_created', table_name='index_errors')
    op.drop_index('idx_index_error_status', table_name='index_errors')
    op.drop_index('idx_index_error_target', table_name='index_errors')
    op.drop_index('idx_index_error_record', table_name='index_errors')

    # Drop table
    op.drop_table('index_errors')
