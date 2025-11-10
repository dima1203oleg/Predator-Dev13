"""
Celery Workers for CDC Pipeline
"""
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from celery import Celery
from celery.schedules import crontab
import psycopg2
import psycopg2.extras
from opensearchpy import OpenSearch
from qdrant_client import QdrantClient
import redis
import json

logger = logging.getLogger(__name__)

# Celery app configuration
celery_app = Celery(
    'predator_cdc',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    include=['etl.cdc_workers']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,

    # Routing
    task_routes={
        'cdc_workers.process_outbox_batch': {'queue': 'cdc'},
        'cdc_workers.sync_to_opensearch': {'queue': 'sync'},
        'cdc_workers.sync_to_qdrant': {'queue': 'sync'},
        'cdc_workers.health_check': {'queue': 'monitoring'}
    },

    # Beat schedule for periodic tasks
    beat_schedule={
        'process-outbox-every-10s': {
            'task': 'cdc_workers.process_outbox_batch',
            'schedule': 10.0,
            'args': (100,)
        },
        'health-check-every-30s': {
            'task': 'cdc_workers.health_check',
            'schedule': 30.0
        },
        'cleanup-old-events-daily': {
            'task': 'cdc_workers.cleanup_processed_events',
            'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        }
    }
)

# Database connections
def get_pg_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        user=os.getenv('POSTGRES_USER', 'predator'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB', 'predator_analytics')
    )

def get_opensearch_client():
    """Get OpenSearch client"""
    return OpenSearch(
        hosts=[os.getenv('OPENSEARCH_HOST', 'localhost:9200')],
        http_auth=(os.getenv('OPENSEARCH_USER', 'admin'),
                  os.getenv('OPENSEARCH_PASSWORD')),
        use_ssl=True,
        verify_certs=False
    )

def get_qdrant_client():
    """Get Qdrant client"""
    return QdrantClient(
        host=os.getenv('QDRANT_HOST', 'localhost'),
        port=int(os.getenv('QDRANT_PORT', '6333'))
    )

def get_redis_client():
    """Get Redis client for caching"""
    return redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

# CDC Worker Tasks
@celery_app.task(bind=True, max_retries=3)
def process_outbox_batch(self, batch_size: int = 100):
    """
    Process batch of outbox events
    """
    try:
        conn = get_pg_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get unprocessed events
        cursor.execute("""
            SELECT * FROM public.get_unprocessed_events(%s)
        """, (batch_size,))

        events = cursor.fetchall()

        if not events:
            logger.debug("No events to process")
            return {"processed": 0}

        processed_ids = []
        failed_ids = []

        for event in events:
            try:
                # Route event to appropriate handler
                if event['aggregate_type'] == 'customs_data':
                    handle_customs_data_event(event)
                elif event['aggregate_type'] == 'company':
                    handle_company_event(event)
                elif event['aggregate_type'] == 'hs_code':
                    handle_hs_code_event(event)

                processed_ids.append(event['id'])

            except Exception as e:
                logger.error(f"Failed to process event {event['id']}: {e}")
                # Mark as failed
                cursor.execute("""
                    SELECT public.mark_outbox_failed(%s, %s)
                """, (event['id'], str(e)))
                failed_ids.append(event['id'])

        # Mark successful events as processed
        if processed_ids:
            cursor.execute("""
                SELECT public.mark_outbox_processed(%s)
            """, (processed_ids,))

        conn.commit()

        logger.info(f"Processed {len(processed_ids)} events, {len(failed_ids)} failed")

        return {
            "processed": len(processed_ids),
            "failed": len(failed_ids),
            "batch_size": batch_size
        }

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        self.retry(countdown=60)
        return {"error": str(e)}

    finally:
        if 'conn' in locals():
            conn.close()

@celery_app.task(bind=True)
def sync_to_opensearch(self, index_name: str, documents: List[Dict[str, Any]]):
    """
    Sync documents to OpenSearch
    """
    try:
        client = get_opensearch_client()

        # Bulk index documents
        actions = []
        for doc in documents:
            actions.extend([
                {"index": {"_index": index_name, "_id": doc["id"]}},
                doc
            ])

        if actions:
            response = client.bulk(actions)
            success_count = response["items"].count(
                lambda x: x["index"]["status"] in (200, 201)
            )

            logger.info(f"Synced {success_count}/{len(documents)} to OpenSearch index {index_name}")
            return {"synced": success_count, "total": len(documents)}

    except Exception as e:
        logger.error(f"OpenSearch sync failed: {e}")
        self.retry(countdown=30)
        return {"error": str(e)}

@celery_app.task(bind=True)
def sync_to_qdrant(self, collection_name: str, vectors: List[Dict[str, Any]]):
    """
    Sync vectors to Qdrant
    """
    try:
        client = get_qdrant_client()

        # Upsert vectors
        points = []
        for vec in vectors:
            points.append({
                "id": vec["id"],
                "vector": vec["vector"],
                "payload": vec["payload"]
            })

        if points:
            client.upsert(
                collection_name=collection_name,
                points=points
            )

            logger.info(f"Synced {len(points)} vectors to Qdrant collection {collection_name}")
            return {"synced": len(points)}

    except Exception as e:
        logger.error(f"Qdrant sync failed: {e}")
        self.retry(countdown=30)
        return {"error": str(e)}

@celery_app.task
def health_check():
    """
    Health check for CDC pipeline
    """
    try:
        results = {}

        # Check PostgreSQL
        try:
            conn = get_pg_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM public.outbox WHERE processed = FALSE")
            pending_count = cursor.fetchone()[0]
            results["postgres"] = {"status": "healthy", "pending_events": pending_count}
            conn.close()
        except Exception as e:
            results["postgres"] = {"status": "unhealthy", "error": str(e)}

        # Check OpenSearch
        try:
            client = get_opensearch_client()
            health = client.cluster.health()
            results["opensearch"] = {
                "status": "healthy" if health["status"] in ("green", "yellow") else "unhealthy",
                "cluster_status": health["status"]
            }
        except Exception as e:
            results["opensearch"] = {"status": "unhealthy", "error": str(e)}

        # Check Qdrant
        try:
            client = get_qdrant_client()
            collections = client.get_collections()
            results["qdrant"] = {
                "status": "healthy",
                "collections_count": len(collections.collections)
            }
        except Exception as e:
            results["qdrant"] = {"status": "unhealthy", "error": str(e)}

        # Check Redis
        try:
            redis_client = get_redis_client()
            redis_client.ping()
            results["redis"] = {"status": "healthy"}
        except Exception as e:
            results["redis"] = {"status": "unhealthy", "error": str(e)}

        # Overall status
        unhealthy_count = sum(1 for r in results.values() if r["status"] == "unhealthy")
        results["overall"] = "healthy" if unhealthy_count == 0 else "degraded"

        logger.info(f"Health check: {results['overall']}")
        return results

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"overall": "error", "error": str(e)}

@celery_app.task
def cleanup_processed_events(days_old: int = 30):
    """
    Clean up old processed events
    """
    try:
        conn = get_pg_connection()
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=days_old)

        cursor.execute("""
            DELETE FROM public.outbox
            WHERE processed = TRUE
              AND processed_at < %s
        """, (cutoff_date,))

        deleted_count = cursor.rowcount
        conn.commit()

        logger.info(f"Cleaned up {deleted_count} old processed events")
        return {"deleted": deleted_count}

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"error": str(e)}

    finally:
        if 'conn' in locals():
            conn.close()

# Event handlers
def handle_customs_data_event(event: Dict[str, Any]):
    """Handle customs data events"""
    event_type = event['event_type']
    payload = event['payload']

    if event_type == 'customs_data.created':
        # Sync to OpenSearch
        doc = {
            "id": payload["id"],
            "hs_code": payload["hs_code"],
            "company_name": payload["company_name"],
            "edrpou": payload["edrpou"],
            "amount": payload["amount"],
            "date": payload["date"],
            "country_code": payload["country_code"],
            "customs_office": payload["customs_office"],
            "created_at": payload["created_at"]
        }

        sync_to_opensearch.delay("customs_data", [doc])

        # Generate and sync vector to Qdrant
        # (This would use the embedding model from model_registry)
        # vector = generate_embedding(f"{doc['company_name']} {doc['hs_code']}")
        # sync_to_qdrant.delay("customs_vectors", [{"id": doc["id"], "vector": vector, "payload": doc}])

    elif event_type == 'customs_data.updated':
        # Update in OpenSearch and Qdrant
        pass

    elif event_type == 'customs_data.deleted':
        # Delete from OpenSearch and Qdrant
        pass

def handle_company_event(event: Dict[str, Any]):
    """Handle company events"""
    # Similar to customs data but for companies index
    pass

def handle_hs_code_event(event: Dict[str, Any]):
    """Handle HS code events"""
    # Similar to customs data but for HS codes index
    pass

# Monitoring utilities
def get_cdc_metrics() -> Dict[str, Any]:
    """Get CDC pipeline metrics"""
    try:
        conn = get_pg_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get outbox stats
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN processed = FALSE THEN 1 END) as pending,
                COUNT(CASE WHEN processed = TRUE THEN 1 END) as processed,
                AVG(EXTRACT(EPOCH FROM (NOW() - created_at))) as avg_processing_time,
                MAX(EXTRACT(EPOCH FROM (NOW() - created_at))) as max_lag
            FROM public.outbox
            WHERE created_at > NOW() - INTERVAL '1 hour'
        """)

        stats = cursor.fetchone()

        # Get Celery stats from Redis
        redis_client = get_redis_client()
        celery_stats = redis_client.hgetall("celery_stats") or {}

        conn.close()

        return {
            "outbox": dict(stats),
            "celery": celery_stats,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {"error": str(e)}

    finally:
        if 'conn' in locals():
            conn.close()
