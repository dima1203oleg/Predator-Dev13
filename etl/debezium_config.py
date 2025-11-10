"""
Debezium PostgreSQL Connector Configuration
"""
import os
from typing import Dict, Any

# Debezium connector config for PostgreSQL CDC
DEBEZIUM_CONFIG = {
    "name": "predator-postgres-connector",
    "config": {
        # Basic connector config
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "tasks.max": "3",

        # PostgreSQL connection
        "database.hostname": os.getenv("POSTGRES_HOST", "localhost"),
        "database.port": os.getenv("POSTGRES_PORT", "5432"),
        "database.user": os.getenv("POSTGRES_USER", "predator"),
        "database.password": os.getenv("POSTGRES_PASSWORD"),
        "database.dbname": os.getenv("POSTGRES_DB", "predator_analytics"),
        "database.server.name": "predator_pg",

        # Schema and table filtering
        "schema.include.list": "public",
        "table.include.list": "public.customs_data,public.companies,public.hs_codes",

        # Column filtering (exclude sensitive data)
        "column.exclude.list": "public.customs_data.sensitive_field",

        # CDC mode
        "plugin.name": "pgoutput",
        "slot.name": "predator_slot",
        "publication.name": "predator_pub",

        # Snapshot config
        "snapshot.mode": "initial",
        "snapshot.locking.mode": "none",

        # Heartbeat for monitoring
        "heartbeat.interval.ms": "60000",
        "heartbeat.topics.prefix": "predator_heartbeat",

        # Topic naming
        "topic.prefix": "predator",
        "topic.creation.enable": "true",
        "topic.creation.default.replication.factor": 3,
        "topic.creation.default.partitions": 6,

        # Message format
        "key.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "key.converter.schemas.enable": "false",
        "value.converter.schemas.enable": "false",

        # Transformations
        "transforms": "unwrap,dropTopicPrefix",
        "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
        "transforms.unwrap.drop.tombstones": "false",
        "transforms.unwrap.delete.handling.mode": "rewrite",
        "transforms.dropTopicPrefix.type": "org.apache.kafka.connect.transforms.RegexRouter",
        "transforms.dropTopicPrefix.regex": "predator\\.(.+)",
        "transforms.dropTopicPrefix.replacement": "$1",

        # Monitoring
        "errors.log.enable": "true",
        "errors.log.include.messages": "true",

        # Performance tuning
        "max.batch.size": 2048,
        "max.queue.size": 8192,
        "poll.interval.ms": 1000,

        # Decimal handling
        "decimal.handling.mode": "double"
    }
}

# Kafka Connect REST API endpoints
KAFKA_CONNECT_URL = os.getenv("KAFKA_CONNECT_URL", "http://localhost:8083")

# Connector management functions
def get_connector_config() -> Dict[str, Any]:
    """Get Debezium connector configuration"""
    return DEBEZIUM_CONFIG

def get_connector_status_url(connector_name: str) -> str:
    """Get URL for connector status"""
    return f"{KAFKA_CONNECT_URL}/connectors/{connector_name}/status"

def get_connector_config_url(connector_name: str) -> str:
    """Get URL for connector config"""
    return f"{KAFKA_CONNECT_URL}/connectors/{connector_name}/config"

# Monitoring queries
MONITORING_QUERIES = {
    "lag_seconds": """
        SELECT
            slot_name,
            active,
            pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) as lag_bytes,
            pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) / 1024 / 1024 as lag_mb,
            EXTRACT(EPOCH FROM (now() - pg_stat_replication.replay_timestamp)) as lag_seconds
        FROM pg_replication_slots
        LEFT JOIN pg_stat_replication ON slot_name = slot_name
        WHERE slot_name = 'predator_slot';
    """,

    "publication_tables": """
        SELECT
            schemaname,
            tablename,
            attname,
            atttypid::regtype
        FROM pg_publication_tables pt
        JOIN pg_attribute pa ON pa.attrelid = pt.tablename::regclass
        WHERE pubname = 'predator_pub'
        ORDER BY schemaname, tablename, attnum;
    """,

    "slot_stats": """
        SELECT
            slot_name,
            database,
            active,
            xmin,
            catalog_xmin,
            restart_lsn,
            confirmed_flush_lsn
        FROM pg_replication_slots
        WHERE slot_name = 'predator_slot';
    """
}
