"""
Docker Compose for CDC Pipeline
"""

# Docker Compose configuration for CDC components
DOCKER_COMPOSE_CDC = """
version: '3.8'

services:
  # Apache Kafka
  kafka:
    image: confluentinc/cp-kafka:7.4.0
    container_name: predator_kafka
    ports:
      - "9092:9092"
      - "9101:9101"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_JMX_PORT: 9101
      KAFKA_JMX_HOSTNAME: localhost
    depends_on:
      - zookeeper
    healthcheck:
      test: ["CMD-SHELL", "kafka-broker-api-versions --bootstrap-server localhost:9092"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Zookeeper
  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    container_name: predator_zookeeper
    ports:
      - "2181:2181"
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  # Kafka Connect with Debezium
  kafka-connect:
    image: debezium/connect:2.4
    container_name: predator_kafka_connect
    ports:
      - "8083:8083"
    environment:
      BOOTSTRAP_SERVERS: kafka:29092
      GROUP_ID: predator_connect
      CONFIG_STORAGE_TOPIC: predator_connect_configs
      OFFSET_STORAGE_TOPIC: predator_connect_offsets
      STATUS_STORAGE_TOPIC: predator_connect_status
      CONFIG_STORAGE_REPLICATION_FACTOR: 1
      OFFSET_STORAGE_REPLICATION_FACTOR: 1
      STATUS_STORAGE_REPLICATION_FACTOR: 1
      KEY_CONVERTER: org.apache.kafka.connect.json.JsonConverter
      VALUE_CONVERTER: org.apache.kafka.connect.json.JsonConverter
      KEY_CONVERTER_SCHEMAS_ENABLE: false
      VALUE_CONVERTER_SCHEMAS_ENABLE: false
      INTERNAL_KEY_CONVERTER: org.apache.kafka.connect.json.JsonConverter
      INTERNAL_VALUE_CONVERTER: org.apache.kafka.connect.json.JsonConverter
      INTERNAL_KEY_CONVERTER_SCHEMAS_ENABLE: false
      INTERNAL_VALUE_CONVERTER_SCHEMAS_ENABLE: false
    depends_on:
      kafka:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8083/ || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Kafka UI for monitoring
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    container_name: predator_kafka_ui
    ports:
      - "8080:8080"
    environment:
      KAFKA_CLUSTERS_0_NAME: predator
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:29092
      KAFKA_CLUSTERS_0_ZOOKEEPER: zookeeper:2181
      DYNAMIC_CONFIG_ENABLED: true
    depends_on:
      - kafka
      - kafka-connect

  # PostgreSQL (if not using external)
  postgres:
    image: postgres:16
    container_name: predator_postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: predator_analytics
      POSTGRES_USER: predator
      POSTGRES_PASSWORD: predator123
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U predator -d predator_analytics"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Redis for Celery
  redis:
    image: redis:7-alpine
    container_name: predator_redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5

volumes:
  postgres_data:
  redis_data:

networks:
  default:
    name: predator_network
"""

# Environment variables for CDC
CDC_ENV_VARS = """
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
KAFKA_CONNECT_URL=http://localhost:8083

# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=predator
POSTGRES_PASSWORD=predator123
POSTGRES_DB=predator_analytics

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# OpenSearch Configuration
OPENSEARCH_HOST=localhost:9200
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=admin123

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
"""

# Docker Compose override for production
DOCKER_COMPOSE_PROD = """
version: '3.8'

services:
  kafka:
    environment:
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 2
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 3
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  kafka-connect:
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  postgres:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
    volumes:
      - postgres_prod_data:/var/lib/postgresql/data

volumes:
  postgres_prod_data:
    driver: local
"""

# Monitoring stack for CDC
MONITORING_STACK = """
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: predator_prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'

  grafana:
    image: grafana/grafana:latest
    container_name: predator_grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin123
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
"""


def get_docker_compose_cdc() -> str:
    """Get CDC Docker Compose configuration"""
    return DOCKER_COMPOSE_CDC


def get_cdc_env_vars() -> str:
    """Get environment variables for CDC"""
    return CDC_ENV_VARS


def get_docker_compose_prod() -> str:
    """Get production Docker Compose override"""
    return DOCKER_COMPOSE_PROD


def get_monitoring_stack() -> str:
    """Get monitoring stack configuration"""
    return MONITORING_STACK
