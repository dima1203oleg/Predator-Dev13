"""Initial schema: datasets, records, entities, OSINT, feedback, voice, timeseries, CDC outbox

Revision ID: 001_initial
Revises:
Create Date: 2025-11-10 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')  # Trigram similarity
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gin"')  # GIN indexes
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")  # TimescaleDB

    # datasets table
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("schema_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("schema_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("checksum", sa.String(64)),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("row_count", sa.BigInteger(), server_default="0"),
        sa.Column("size_bytes", sa.BigInteger(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
    )
    op.create_index("idx_dataset_owner", "datasets", ["owner"])
    op.create_index("idx_dataset_type", "datasets", ["type"])
    op.create_index("idx_dataset_created", "datasets", ["created_at"])

    # records table
    op.create_table(
        "records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pk", sa.String(255), nullable=False),
        sa.Column("op_hash", sa.String(64), nullable=False),
        sa.Column("hs_code", sa.String(10)),
        sa.Column("date", sa.Date()),
        sa.Column("amount", sa.Numeric(18, 2)),
        sa.Column("qty", sa.Float()),
        sa.Column("country_code", sa.String(3)),
        sa.Column("edrpou", sa.String(20)),
        sa.Column("company_name", sa.String(500)),
        sa.Column("customs_office", sa.String(100)),
        sa.Column("attrs", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("source_file", sa.String(500)),
        sa.Column("source_row", sa.Integer()),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("pk", "op_hash", name="uq_record_pk_op_hash"),
    )
    op.create_index("idx_record_dataset", "records", ["dataset_id"])
    op.create_index("idx_record_hs_code", "records", ["hs_code"])
    op.create_index("idx_record_date", "records", ["date"])
    op.create_index("idx_record_country", "records", ["country_code"])
    op.create_index("idx_record_edrpou", "records", ["edrpou"])
    op.create_index("idx_record_amount", "records", ["amount"])
    op.create_index("idx_record_op_hash", "records", ["op_hash"])
    op.create_index("idx_record_attrs_gin", "records", ["attrs"], postgresql_using="gin")

    # entities table
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_key", sa.String(255), nullable=False, unique=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("edrpou", sa.String(20)),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("name_normalized", sa.String(500)),
        sa.Column("attrs", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("confidence_score", sa.Float(), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint("canonical_key", name="uq_entity_canonical_key"),
    )
    op.create_index("idx_entity_type", "entities", ["entity_type"])
    op.create_index("idx_entity_edrpou", "entities", ["edrpou"])
    op.create_index("idx_entity_name", "entities", ["name"])
    op.create_index("idx_entity_attrs_gin", "entities", ["attrs"], postgresql_using="gin")

    # osint_logs table
    op.create_table(
        "osint_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(255)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_tsv", sa.Text()),  # Full-text search vector
        sa.Column("ner_entities", postgresql.JSONB(), server_default="{}"),
        sa.Column("author", sa.String(255)),
        sa.Column("channel", sa.String(255)),
        sa.Column("url", sa.String(1000)),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_data", postgresql.JSONB(), server_default="{}"),
    )
    op.create_index("idx_osint_source", "osint_logs", ["source"])
    op.create_index("idx_osint_collected_at", "osint_logs", ["collected_at"])
    op.create_index(
        "idx_osint_entities_gin", "osint_logs", ["ner_entities"], postgresql_using="gin"
    )

    # feedback table
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("query_vector", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("response_id", postgresql.UUID(as_uuid=True)),
        sa.Column("retrieved_docs", postgresql.JSONB(), server_default="[]"),
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column("relevance_score", sa.Float()),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("agent_name", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
    )
    op.create_index("idx_feedback_user", "feedback", ["user_id"])
    op.create_index("idx_feedback_model", "feedback", ["model_version"])
    op.create_index("idx_feedback_created", "feedback", ["created_at"])

    # voice_logs table
    op.create_table(
        "voice_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("audio_file", sa.String(500)),
        sa.Column("transcript", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("text_input", sa.Text()),
        sa.Column("audio_output", sa.String(500)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("model_version", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
    )
    op.create_index("idx_voice_user", "voice_logs", ["user_id"])
    op.create_index("idx_voice_direction", "voice_logs", ["direction"])
    op.create_index("idx_voice_created", "voice_logs", ["created_at"])

    # timeseries_records table (TimescaleDB hypertable)
    op.create_table(
        "timeseries_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("aggregation", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_ts_metric_time", "timeseries_records", ["metric_name", "time"])
    op.create_index(
        "idx_ts_dimensions", "timeseries_records", ["dimensions"], postgresql_using="gin"
    )

    # Convert to hypertable
    op.execute("SELECT create_hypertable('timeseries_records', 'time', if_not_exists => TRUE)")

    # cdc_outbox table
    op.create_table(
        "cdc_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
    )
    op.create_index("idx_outbox_status", "cdc_outbox", ["status"])
    op.create_index("idx_outbox_created", "cdc_outbox", ["created_at"])

    # query_patterns table
    op.create_table(
        "query_patterns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pattern_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("query_template", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(100)),
        sa.Column("usage_count", sa.Integer(), server_default="1"),
        sa.Column("avg_relevance", sa.Float()),
        sa.Column("training_status", sa.String(20), server_default="pending"),
        sa.Column("model_version", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("idx_query_pattern_hash", "query_patterns", ["pattern_hash"])
    op.create_index("idx_query_pattern_created", "query_patterns", ["created_at"])

    # ========== CDC TRIGGERS ==========
    # Trigger for records → cdc_outbox
    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_record_change()
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO cdc_outbox (id, event_type, aggregate_id, payload, status, created_at)
            VALUES (
                uuid_generate_v4(),
                'record.' || TG_OP,
                NEW.id,
                row_to_json(NEW),
                'pending',
                NOW()
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_record_change
        AFTER INSERT OR UPDATE ON records
        FOR EACH ROW EXECUTE FUNCTION notify_record_change();
    """
    )

    # Trigger for entities → cdc_outbox
    op.execute(
        """
        CREATE TRIGGER trigger_entity_change
        AFTER INSERT OR UPDATE ON entities
        FOR EACH ROW EXECUTE FUNCTION notify_record_change();
    """
    )

    # ========== FULL-TEXT SEARCH TRIGGER ==========
    # Trigger for osint_logs text → text_tsv
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_text_tsv()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.text_tsv := to_tsvector('ukrainian', NEW.text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_osint_text_tsv
        BEFORE INSERT OR UPDATE OF text ON osint_logs
        FOR EACH ROW EXECUTE FUNCTION update_text_tsv();
    """
    )

    # Create FTS index
    op.execute("CREATE INDEX idx_osint_text_fts ON osint_logs USING gin(text_tsv)")


def downgrade():
    op.drop_table("query_patterns")
    op.drop_table("cdc_outbox")
    op.execute("DROP TABLE IF EXISTS timeseries_records CASCADE")
    op.drop_table("voice_logs")
    op.drop_table("feedback")
    op.drop_table("osint_logs")
    op.drop_table("entities")
    op.drop_table("records")
    op.drop_table("datasets")

    op.execute("DROP FUNCTION IF EXISTS notify_record_change CASCADE")
    op.execute("DROP FUNCTION IF EXISTS update_text_tsv CASCADE")
