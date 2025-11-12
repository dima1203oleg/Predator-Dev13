"""
Database Models for Predator Analytics v13
Comprehensive schema: datasets, records, entities, OSINT, feedback, voice logs
"""

import uuid

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.database import Base


# ==================== DATASETS ====================
class Dataset(Base):
    """Dataset registry: metadata, schema, ownership"""

    __tablename__ = "datasets"
    __table_args__ = (
        Index("idx_dataset_owner", "owner"),
        Index("idx_dataset_type", "type"),
        Index("idx_dataset_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    type = Column(String(50), nullable=False)  # customs/tax/registry/osint
    description = Column(Text)
    schema_json = Column(JSONB, nullable=False, default={})
    schema_version = Column(String(20), nullable=False, default="1.0")
    checksum = Column(String(64))  # SHA256 of schema
    owner = Column(String(255), nullable=False)
    status = Column(String(20), default="active")  # active/archived
    row_count = Column(BigInteger, default=0)
    size_bytes = Column(BigInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    extra_metadata = Column(JSONB, default={})  # Renamed from 'metadata'

    # Relationships
    records = relationship("Record", back_populates="dataset", cascade="all, delete-orphan")


# ==================== RECORDS (Customs/Tax/etc) ====================
class Record(Base):
    """Universal records table with flexible JSONB attrs"""

    __tablename__ = "records"
    __table_args__ = (
        UniqueConstraint("pk", "op_hash", name="uq_record_pk_op_hash"),
        Index("idx_record_dataset", "dataset_id"),
        Index("idx_record_hs_code", "hs_code"),
        Index("idx_record_date", "date"),
        Index("idx_record_country", "country_code"),
        Index("idx_record_edrpou", "edrpou"),
        Index("idx_record_amount", "amount"),
        Index("idx_record_op_hash", "op_hash"),
        Index("idx_record_attrs_gin", "attrs", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )

    # Business key + operation hash for deduplication
    pk = Column(String(255), nullable=False)  # Business primary key
    op_hash = Column(String(64), nullable=False, index=True)  # SHA256(concat all fields)

    # Common structured fields
    hs_code = Column(String(10))  # HS commodity code
    date = Column(Date)
    amount = Column(Numeric(18, 2))  # USD amount
    qty = Column(Float)
    country_code = Column(String(3))  # ISO 3166-1 alpha-3
    edrpou = Column(String(20))  # Company tax ID
    company_name = Column(String(500))
    customs_office = Column(String(100))

    # Flexible JSONB for dataset-specific fields
    attrs = Column(JSONB, nullable=False, default={})

    # Metadata
    source_file = Column(String(500))
    source_row = Column(Integer)
    imported_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    dataset = relationship("Dataset", back_populates="records")


# ==================== ENTITIES (Canonical Registry) ====================
class Entity(Base):
    """Canonical entity registry: companies, officials, lobbyists"""

    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("canonical_key", name="uq_entity_canonical_key"),
        Index("idx_entity_type", "entity_type"),
        Index("idx_entity_edrpou", "edrpou"),
        Index("idx_entity_name", "name"),
        Index("idx_entity_attrs_gin", "attrs", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_key = Column(
        String(255), nullable=False, unique=True
    )  # edrpou:12345678 or name_normalized
    entity_type = Column(String(50), nullable=False)  # company/official/lobbyist

    # Core fields
    edrpou = Column(String(20), index=True)
    name = Column(String(500), nullable=False)
    name_normalized = Column(String(500))  # Lowercase, stripped

    # Flexible attrs (OSINT enrichment, NER, registries)
    attrs = Column(JSONB, nullable=False, default={})
    # Example attrs: {address, phone, email, ownership, declarations, telegram_mentions, sanctions, ...}

    # Metadata
    confidence_score = Column(Float, default=1.0)  # Entity resolution confidence
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ==================== OSINT LOGS ====================
class OsintLog(Base):
    """OSINT collection logs: Telegram, websites, social media"""

    __tablename__ = "osint_logs"
    __table_args__ = (
        Index("idx_osint_source", "source"),
        Index("idx_osint_collected_at", "collected_at"),
        Index("idx_osint_entities_gin", "ner_entities", postgresql_using="gin"),
        Index("idx_osint_text_fts", "text_tsv", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(100), nullable=False)  # telegram/website/twitter
    source_id = Column(String(255))  # Message ID, URL, Tweet ID

    # Content
    text = Column(Text, nullable=False)
    text_tsv = Column(Text)  # Full-text search vector (generated by trigger)

    # NER extraction
    ner_entities = Column(JSONB, default={})  # {persons: [], orgs: [], locations: [], ...}

    # Metadata
    author = Column(String(255))
    channel = Column(String(255))
    url = Column(String(1000))
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    raw_data = Column(JSONB, default={})


# ==================== FEEDBACK (Self-Learning) ====================
class Feedback(Base):
    """User feedback for query relevance (self-learning dataset)"""

    __tablename__ = "feedback"
    __table_args__ = (
        Index("idx_feedback_user", "user_id"),
        Index("idx_feedback_model", "model_version"),
        Index("idx_feedback_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)

    # Query context
    query_text = Column(Text, nullable=False)
    query_vector = Column(ARRAY(Float), nullable=False)  # Embedding for similarity

    # Response
    response_id = Column(UUID(as_uuid=True))
    retrieved_docs = Column(JSONB, default=[])  # List of doc IDs/scores

    # Label
    label = Column(String(20), nullable=False)  # relevant/not_relevant/partially_relevant
    relevance_score = Column(Float)  # 0.0-1.0

    # Model context
    model_version = Column(String(50), nullable=False)
    agent_name = Column(String(100))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    extra_metadata = Column(JSONB, default={})  # Renamed from 'metadata'


# ==================== VOICE LOGS ====================
class VoiceLog(Base):
    """Voice interaction logs for STT/TTS quality monitoring"""

    __tablename__ = "voice_logs"
    __table_args__ = (
        Index("idx_voice_user", "user_id"),
        Index("idx_voice_direction", "direction"),
        Index("idx_voice_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)

    # Direction: stt (speech-to-text) or tts (text-to-speech)
    direction = Column(String(10), nullable=False)  # stt/tts

    # STT specific
    audio_file = Column(String(500))  # MinIO path
    transcript = Column(Text)
    confidence = Column(Float)  # 0.0-1.0

    # TTS specific
    text_input = Column(Text)
    audio_output = Column(String(500))  # MinIO path

    # Performance
    latency_ms = Column(Integer)
    model_version = Column(String(50))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    extra_metadata = Column(JSONB, default={}) # Renamed from 'metadata'


# ==================== TIME-SERIES (Timescale) ====================
class TimeSeriesRecord(Base):
    """Time-series table (Timescale hypertable) for forecasting"""

    __tablename__ = "timeseries_records"
    __table_args__ = (
        Index("idx_ts_metric_time", "metric_name", "time"),
        Index("idx_ts_dimensions", "dimensions", postgresql_using="gin"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False)
    metric_name = Column(String(100), nullable=False)  # import_amount/export_qty/...
    value = Column(Float, nullable=False)

    # Dimensions (hs_code, country, etc)
    dimensions = Column(JSONB, nullable=False, default={})

    # Aggregation metadata
    aggregation = Column(String(20))  # daily/weekly/monthly
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ==================== CDC OUTBOX ====================
class CdcOutbox(Base):
    """CDC Outbox pattern for reliable event publishing"""

    __tablename__ = "cdc_outbox"
    __table_args__ = (
        Index("idx_outbox_status", "status"),
        Index("idx_outbox_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)  # record.created/entity.updated
    aggregate_id = Column(UUID(as_uuid=True), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), default="pending")  # pending/processing/done/failed
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    error = Column(Text)


# ==================== QUERY PATTERNS (Self-Learning) ====================
class QueryPattern(Base):
    """Learned query patterns for LoRA training"""

    __tablename__ = "query_patterns"
    __table_args__ = (
        Index("idx_query_pattern_hash", "pattern_hash"),
        Index("idx_query_pattern_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_hash = Column(String(64), nullable=False, unique=True)

    # Pattern
    query_template = Column(Text, nullable=False)
    intent = Column(String(100))  # search/forecast/corruption/lobby

    # Statistics
    usage_count = Column(Integer, default=1)
    avg_relevance = Column(Float)

    # LoRA training status
    training_status = Column(String(20), default="pending")  # pending/training/deployed
    model_version = Column(String(50))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ==================== INDEX ERRORS (DLQ) ====================
class IndexError(Base):
    """Dead Letter Queue for failed indexing operations"""

    __tablename__ = "index_errors"
    __table_args__ = (
        Index("idx_index_error_record", "record_id"),
        Index("idx_index_error_target", "target_db"),
        Index("idx_index_error_status", "status"),
        Index("idx_index_error_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id = Column(
        UUID(as_uuid=True), ForeignKey("records.id", ondelete="CASCADE"), nullable=False
    )

    # Target database that failed
    target_db = Column(String(50), nullable=False)  # opensearch/qdrant/neo4j/redis

    # Error details
    operation = Column(String(50), nullable=False)  # index/upsert/merge/cache
    error_message = Column(Text, nullable=False)
    error_type = Column(String(100))  # ConnectionError/TimeoutError/ValidationError
    stack_trace = Column(Text)

    # Retry logic
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    status = Column(String(20), default="pending")  # pending/retrying/failed/resolved
    next_retry_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))

    # Context
    payload_snapshot = Column(JSONB, default={})  # Snapshot of data for retry

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    record = relationship("Record", backref="index_errors")
