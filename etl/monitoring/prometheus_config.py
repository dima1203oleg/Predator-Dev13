"""
Prometheus Configuration for CDC Pipeline Monitoring
"""
import os

# Prometheus configuration
PROMETHEUS_CONFIG = """
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # PostgreSQL Exporter
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:9187']
    scrape_interval: 30s

  # Redis Exporter
  - job_name: 'redis'
    static_configs:
      - targets: ['redis:9121']
    scrape_interval: 30s

  # Kafka Exporter
  - job_name: 'kafka'
    static_configs:
      - targets: ['kafka:9308']
    scrape_interval: 30s

  # OpenSearch Exporter
  - job_name: 'opensearch'
    static_configs:
      - targets: ['opensearch:9114']
    scrape_interval: 30s

  # Qdrant (custom metrics endpoint)
  - job_name: 'qdrant'
    static_configs:
      - targets: ['qdrant:6333']
    metrics_path: '/metrics'
    scrape_interval: 30s

  # Celery Workers
  - job_name: 'celery'
    static_configs:
      - targets: ['celery-exporter:9808']
    scrape_interval: 30s

  # CDC Lag Monitor (custom)
  - job_name: 'cdc_lag'
    static_configs:
      - targets: ['cdc-monitor:8080']
    scrape_interval: 10s

  # Node Exporter (system metrics)
  - job_name: 'node'
    static_configs:
      - targets:
        - 'kafka:9100'
        - 'postgres:9100'
        - 'redis:9100'
    scrape_interval: 30s
"""

# Alert rules for CDC pipeline
ALERT_RULES = """
groups:
  - name: cdc_pipeline_alerts
    rules:
      # PostgreSQL alerts
      - alert: PostgresDown
        expr: up{job="postgres"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL is down"
          description: "PostgreSQL has been down for more than 5 minutes."

      - alert: PostgresReplicationLag
        expr: pg_replication_lag > 100
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "PostgreSQL replication lag is high"
          description: "Replication lag is {{ $value }} seconds."

      # Kafka alerts
      - alert: KafkaDown
        expr: up{job="kafka"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Kafka is down"
          description: "Kafka has been down for more than 5 minutes."

      - alert: KafkaUnderReplicatedPartitions
        expr: kafka_partition_under_replicated_partition > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Kafka has under-replicated partitions"
          description: "{{ $value }} partitions are under-replicated."

      # OpenSearch alerts
      - alert: OpenSearchDown
        expr: up{job="opensearch"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "OpenSearch is down"
          description: "OpenSearch has been down for more than 5 minutes."

      - alert: OpenSearchClusterRed
        expr: opensearch_cluster_status{status="red"} == 1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "OpenSearch cluster is red"
          description: "OpenSearch cluster health is red."

      # Qdrant alerts
      - alert: QdrantDown
        expr: up{job="qdrant"} == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Qdrant is down"
          description: "Qdrant has been down for more than 5 minutes."

      # CDC Lag alerts
      - alert: HighCDCLag
        expr: cdc_lag_seconds > 60
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "CDC lag is high"
          description: "CDC processing lag is {{ $value }} seconds."

      - alert: CDCPipelineStuck
        expr: increase(cdc_processed_events_total[5m]) == 0
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "CDC pipeline is stuck"
          description: "No events processed in the last 10 minutes."

      # Celery alerts
      - alert: CeleryWorkerDown
        expr: celery_workers_total < 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Celery workers are down"
          description: "No active Celery workers detected."

      - alert: CeleryTaskFailureRate
        expr: rate(celery_task_failed_total[5m]) / rate(celery_task_sent_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High Celery task failure rate"
          description: "Celery task failure rate is {{ $value | humanizePercentage }}."

  - name: business_metrics_alerts
    rules:
      - alert: LowIngestionRate
        expr: rate(customs_records_ingested_total[5m]) < 10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low data ingestion rate"
          description: "Data ingestion rate dropped below 10 records/minute."

      - alert: HighErrorRate
        expr: rate(parsing_errors_total[5m]) / rate(parsing_attempts_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High parsing error rate"
          description: "Parsing error rate is {{ $value | humanizePercentage }}."
"""

# Grafana dashboard configuration
GRAFANA_DASHBOARD = """
{
  "dashboard": {
    "title": "Predator Analytics CDC Pipeline",
    "tags": ["predator", "cdc", "monitoring"],
    "timezone": "UTC",
    "panels": [
      {
        "title": "CDC Pipeline Overview",
        "type": "stat",
        "targets": [
          {
            "expr": "cdc_processed_events_total",
            "legendFormat": "Processed Events"
          }
        ]
      },
      {
        "title": "CDC Lag",
        "type": "graph",
        "targets": [
          {
            "expr": "cdc_lag_seconds",
            "legendFormat": "Lag (seconds)"
          }
        ]
      },
      {
        "title": "System Resources",
        "type": "graph",
        "targets": [
          {
            "expr": "100 - (avg by(instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "legendFormat": "CPU Usage %"
          },
          {
            "expr": "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes",
            "legendFormat": "Memory Usage"
          }
        ]
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
"""

def get_prometheus_config() -> str:
    """Get Prometheus configuration"""
    return PROMETHEUS_CONFIG

def get_alert_rules() -> str:
    """Get alert rules configuration"""
    return ALERT_RULES

def get_grafana_dashboard() -> str:
    """Get Grafana dashboard configuration"""
    return GRAFANA_DASHBOARD
