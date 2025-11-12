import os
from datetime import datetime
from typing import List

import redis
import requests  # For Ollama integration
from neo4j import GraphDatabase
from opensearchpy import OpenSearch
from opensearchpy import helpers as opensearch_helpers
from qdrant_client.models import Distance
from sqlalchemy.orm import Session

from api.database import Base, SessionLocal, engine
from api.models import Dataset, Record
from api.qdrant_manager import QdrantManager
from parsers.excel_parser import ExcelParser

# Ensure all tables are created (if not already)
Base.metadata.create_all(bind=engine)

class MultiDatabaseIndexer:
    """Індексує дані у всі бази даних з дедуплікацією"""

    def __init__(self, db_session: Session = None):
        # Configuration from environment variables
        self.opensearch_host = os.getenv("OPENSEARCH_HOST", "localhost")
        self.opensearch_user = os.getenv("OPENSEARCH_USER", "admin")
        self.opensearch_password = os.getenv("OPENSEARCH_PASSWORD", "admin")
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION", "customs_records_v1")
        self.qdrant_vector_size = int(os.getenv("QDRANT_VECTOR_SIZE", 768))
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

        # Database session for DLQ logging
        self.db_session = db_session

        # OpenSearch
        self.opensearch = OpenSearch(
            hosts=[{"host": self.opensearch_host, "port": 9200}],
            http_auth=(self.opensearch_user, self.opensearch_password),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False
        )

        # Qdrant
        self.qdrant_manager = QdrantManager(
            host=self.qdrant_host,
            port=self.qdrant_port,
            collection_name=self.qdrant_collection
        )

        # Neo4j
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )

        # Redis
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=0,
            decode_responses=True
        )

        print("✅ Initialized all database connections")

    def setup_opensearch_aliases(self):
        """Створює aliases для OpenSearch: write/read/safe"""
        try:
            index_name = "customs_records"

            # Write alias (для індексації)
            write_alias = {
                "actions": [
                    {
                        "add": {
                            "index": index_name,
                            "alias": "pa-customs-write",
                            "is_write_index": True
                        }
                    }
                ]
            }

            # Read alias (для пошуку)
            read_alias = {
                "actions": [
                    {
                        "add": {
                            "index": index_name,
                            "alias": "pa-customs-read"
                        }
                    }
                ]
            }

            # Safe alias (з PII маскуванням)
            safe_alias = {
                "actions": [
                    {
                        "add": {
                            "index": index_name,
                            "alias": "pa-customs-safe"
                        }
                    }
                ]
            }

            # Apply aliases
            for alias_name, alias_body in [
                ("write", write_alias),
                ("read", read_alias),
                ("safe", safe_alias)
            ]:
                try:
                    self.opensearch.indices.update_aliases(body=alias_body)
                    print(f"✅ OpenSearch alias 'pa-customs-{alias_name}' created")
                except Exception as e:
                    print(f"⚠️ Failed to create alias 'pa-customs-{alias_name}': {e}")

        except Exception as e:
            print(f"⚠️ Error setting up OpenSearch aliases: {e}")

    def setup_opensearch_pii_pipeline(self):
        """Створює ingest pipeline для PII маскування"""
        try:
            pipeline_body = {
                "description": "Mask PII fields for safe alias",
                "processors": [
                    {
                        "set": {
                            "field": "edrpou_masked",
                            "value": "***",
                            "if": "ctx.edrpou != null"
                        }
                    },
                    {
                        "set": {
                            "field": "company_name_masked",
                            "value": "REDACTED",
                            "if": "ctx.company_name != null"
                        }
                    },
                    {
                        "remove": {
                            "field": ["edrpou", "company_name"],
                            "if": "ctx._index == 'pa-customs-safe'"
                        }
                    }
                ]
            }

            self.opensearch.ingest.put_pipeline(
                id="pii_masking_pipeline",
                body=pipeline_body
            )
            print("✅ OpenSearch PII masking pipeline created")

        except Exception as e:
            print(f"⚠️ Failed to create PII pipeline: {e}")

    def _log_index_error(self, record: Record, target_db: str, operation: str, error: Exception):
        """Логує помилки індексації у DLQ таблицю"""
        try:

            from api.models import IndexError

            # Get db session from indexer
            db_session = getattr(self, 'db_session', None)
            if not db_session:
                print(f"⚠️ Cannot log DLQ error - no db session: {target_db}/{operation}: {error}")
                return

            dlq_entry = IndexError(
                record_id=record.id,
                target_db=target_db,
                operation=operation,
                error_message=str(error),
                retry_count=0
            )
            db_session.add(dlq_entry)
            db_session.commit()

        except Exception as dlq_error:
            print(f"⚠️ Failed to log DLQ error: {dlq_error}")

    def reindex_from_postgres(self, dataset_id: str, batch_size: int = 1000):
        """Повний reindex з PostgreSQL у всі цільові БД"""
        try:
            from api.models import Record

            print(f"🔄 Starting full reindex for dataset {dataset_id}")

            # Отримуємо всі записи датасету
            records = self.db_session.query(Record).filter(Record.dataset_id == dataset_id).all()
            total_records = len(records)

            print(f"📊 Found {total_records} records to reindex")

            # Reindex у батчах
            for i in range(0, total_records, batch_size):
                batch = records[i:i + batch_size]
                print(f"  Processing batch {i//batch_size + 1}/{(total_records + batch_size - 1)//batch_size}")

                # OpenSearch
                os_count = self.index_to_opensearch(batch)

                # Qdrant (перегенеруємо embeddings)
                qdrant_count = self.index_to_qdrant(batch)

                # Neo4j
                neo4j_count = self.index_to_neo4j(batch)

                # Redis
                redis_count = self.cache_to_redis(batch)

                print(f"    Batch results: OS={os_count}, Qdrant={qdrant_count}, Neo4j={neo4j_count}, Redis={redis_count}")

            print(f"✅ Reindex completed for dataset {dataset_id}")
            return True

        except Exception as e:
            print(f"❌ Reindex failed: {e}")
            return False

    def consistency_check(self, dataset_id: str, sample_size: int = 100):
        """Перевірка консистентності між БД"""
        try:
            from api.models import Record

            print(f"🔍 Starting consistency check for dataset {dataset_id}")

            # Підрахуємо в PG
            pg_count = self.db_session.query(Record).filter(Record.dataset_id == dataset_id).count()
            print(f"📊 PostgreSQL: {pg_count} records")

            # OpenSearch
            try:
                os_result = self.opensearch.count(index="customs_records", body={"query": {"match_all": {}}})
                os_count = os_result['count']
                print(f"🔍 OpenSearch: {os_count} documents")
            except Exception as e:
                print(f"⚠️ OpenSearch count failed: {e}")
                os_count = 0

            # Qdrant
            try:
                qdrant_info = self.qdrant_manager.get_collection_info()
                qdrant_count = qdrant_info.get('points_count', 0)
                print(f"🧮 Qdrant: {qdrant_count} vectors")
            except Exception as e:
                print(f"⚠️ Qdrant count failed: {e}")
                qdrant_count = 0

            # Neo4j (підрахуємо IMPORTS зв'язки)
            try:
                with self.neo4j_driver.session() as session:
                    result = session.run("MATCH ()-[r:IMPORTS]-() RETURN count(r) as count")
                    neo4j_count = result.single()['count']
                    print(f"🕸️ Neo4j: {neo4j_count} IMPORTS relationships")
            except Exception as e:
                print(f"⚠️ Neo4j count failed: {e}")
                neo4j_count = 0

            # Sample check (порівнюємо op_hash)
            if sample_size > 0:
                sample_records = self.db_session.query(Record).filter(Record.dataset_id == dataset_id).limit(sample_size).all()
                mismatches = 0

                for record in sample_records:
                    record_id = str(record.id)

                    # Check OpenSearch
                    try:
                        os_doc = self.opensearch.get(index="customs_records", id=record_id)
                        if os_doc['_source']['op_hash'] != record.op_hash:
                            mismatches += 1
                    except Exception:
                        mismatches += 1

                    # Check Qdrant
                    try:
                        qdrant_results = self.qdrant_manager.search_similar([0.1] * 768, limit=1, filters={"pk": record.pk})
                        if not qdrant_results or qdrant_results[0]['payload']['op_hash'] != record.op_hash:
                            mismatches += 1
                    except Exception:
                        mismatches += 1

                print(f"🔍 Sample check ({sample_size} records): {mismatches} mismatches")

            # Summary
            print("\n📈 Consistency Summary:")
            print(f"  PostgreSQL: {pg_count}")
            print(f"  OpenSearch: {os_count} ({'✓' if os_count == pg_count else '✗'})")
            print(f"  Qdrant: {qdrant_count} ({'✓' if qdrant_count == pg_count else '✗'})")
            print(f"  Neo4j: {neo4j_count} ({'✓' if neo4j_count == pg_count else '✗'})")

            return {
                'pg_count': pg_count,
                'os_count': os_count,
                'qdrant_count': qdrant_count,
                'neo4j_count': neo4j_count,
                'consistent': pg_count == os_count == qdrant_count == neo4j_count
            }

        except Exception as e:
            print(f"❌ Consistency check failed: {e}")
            return None

    def _embed_text(self, text: str) -> List[float]:
        """Generates embeddings for a given text using Ollama."""
        try:
            r = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.ollama_embed_model, "prompt": text},
                timeout=60
            )
            r.raise_for_status()
            return r.json()["embedding"]
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Ollama embedding error: {e}")
            return [] # Return empty list on error

    def _make_text_for_embedding(self, record: Record) -> str:
        """
        Concatenates informative fields from a record to create text for embedding.
        Handles None values and trims extra spaces.
        """
        parts = [
            record.company_name,
            record.hs_code,
            record.customs_office,
            record.edrpou,
            record.country_code
        ]
        # Filter out None values and join with a single space
        return " ".join(filter(None, parts)).strip()

    def ensure_opensearch_index(self):
        """Створює індекс OpenSearch якщо не існує"""
        index_name = "customs_records"

        if not self.opensearch.indices.exists(index=index_name):
            index_body = {
                "settings": {
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                    "analysis": {
                        "analyzer": {
                            "ukrainian_analyzer": {
                                "type": "standard",
                                "stopwords": "_ukrainian_"
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "record_id": {"type": "keyword"},
                        "op_hash": {"type": "keyword"},
                        "hs_code": {"type": "keyword"},
                        "date": {"type": "date"},
                        "amount": {"type": "double"},
                        "qty": {"type": "double"},
                        "country_code": {"type": "keyword"},
                        "edrpou": {"type": "keyword"},
                        "company_name": {
                            "type": "text",
                            "analyzer": "ukrainian_analyzer",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "customs_office": {
                            "type": "text",
                            "analyzer": "ukrainian_analyzer",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "full_text": {"type": "text", "analyzer": "ukrainian_analyzer"},
                        "indexed_at": {"type": "date"}
                    }
                }
            }

            self.opensearch.indices.create(index=index_name, body=index_body)
            print(f"✅ Created OpenSearch index: {index_name}")
        else:
            print(f"✓ OpenSearch index already exists: {index_name}")

    def ensure_qdrant_collection(self):
        """Створює колекцію Qdrant якщо не існує"""
        try:
            self.qdrant_manager.create_collection(
                vector_size=self.qdrant_vector_size, # Use configured vector size
                distance=Distance.COSINE,
                recreate=False
            )
            print("✅ Qdrant collection ready")
        except Exception as e:
            print(f"⚠️ Qdrant collection setup: {e}")

    def index_to_opensearch(self, records: List[Record]):
        """Індексує записи у OpenSearch"""
        if not records:
            return 0

        actions = []
        record_map = {}  # Map action index to record

        for idx, record in enumerate(records):
            # Створюємо повнотекстовий контент
            full_text = f"{record.company_name or ''} {record.hs_code or ''} {record.customs_office or ''} {record.edrpou or ''}"

            doc = {
                "_index": "customs_records",
                "_id": str(record.id),
                "_source": {
                    "record_id": str(record.id),
                    "op_hash": record.op_hash,
                    "hs_code": record.hs_code,
                    "date": record.date.isoformat() if record.date else None,
                    "amount": float(record.amount) if record.amount else None,
                    "qty": float(record.qty) if record.qty else None,
                    "country_code": record.country_code,
                    "edrpou": record.edrpou,
                    "company_name": record.company_name,
                    "customs_office": record.customs_office,
                    "full_text": full_text,
                    "indexed_at": datetime.now().isoformat()
                }
            }
            actions.append(doc)
            record_map[idx] = record

        success, failed = opensearch_helpers.bulk(self.opensearch, actions, raise_on_error=False)

        # Log failed items to DLQ
        if isinstance(failed, list) and failed:
            for fail_item in failed:
                action_idx = fail_item.get('index', 0)
                if action_idx in record_map:
                    error_msg = fail_item.get('error', 'Unknown error')
                    self._log_index_error(
                        record_map[action_idx],
                        'opensearch',
                        'bulk_index',
                        Exception(str(error_msg))
                    )

        print(f"✅ OpenSearch: indexed {success} records, failed {len(failed) if isinstance(failed, list) else 0}")
        return success

    def index_to_qdrant(self, records: List[Record]):
        """Індексує записи у Qdrant (векторний пошук)"""
        if not records:
            return 0

        points = []
        failed_records = []

        for record in records:
            try:
                text_for_embedding = self._make_text_for_embedding(record)
                embedding = self._embed_text(text_for_embedding)

                if not embedding:
                    print(f"⚠️ Skipping Qdrant indexing for record {record.id} due to embedding error.")
                    self._log_index_error(record, 'qdrant', 'embed', Exception("Empty embedding returned"))
                    failed_records.append(record)
                    continue

                point = {
                    "id": str(record.id),
                    "vector": embedding,
                    "payload": {
                        "pk": record.pk,
                        "title": f"{record.company_name} - {record.hs_code}",
                        "tags": ["customs", record.country_code or "unknown"],
                        "meta": {
                            "hs_code": record.hs_code,
                            "amount": float(record.amount) if record.amount else 0,
                            "date": record.date.isoformat() if record.date else None
                        }
                    }
                }
                points.append(point)

            except Exception as e:
                print(f"⚠️ Failed to prepare Qdrant point for record {record.id}: {e}")
                self._log_index_error(record, 'qdrant', 'prepare_point', e)
                failed_records.append(record)

        if points:
            stats = self.qdrant_manager.upsert_vectors(points, batch_size=100)
            print(f"✅ Qdrant: upserted {stats['upserted']} vectors, skipped {stats['skipped']}, failed {stats['failed']}")
            return stats['upserted']
        return 0

    def index_to_neo4j(self, records: List[Record]):
        """Індексує записи у Neo4j (графова БД)"""
        if not records:
            return 0

        indexed = 0
        with self.neo4j_driver.session() as session:
            for record in records:
                try:
                    # Створюємо вузли та зв'язки
                    query = """
                    MERGE (c:Company {edrpou: $edrpou, name: $company_name})
                    MERGE (p:Product {hs_code: $hs_code})
                    MERGE (co:Country {code: $country_code})
                    MERGE (c)-[r:IMPORTS {
                        amount: $amount,
                        qty: $qty,
                        date: date($date),
                        record_id: $record_id
                    }]->(p)
                    MERGE (p)-[:FROM_COUNTRY]->(co)
                    """

                    session.run(query, {
                        "edrpou": record.edrpou or "UNKNOWN",
                        "company_name": record.company_name or "Unknown Company",
                        "hs_code": record.hs_code or "0000",
                        "country_code": record.country_code or "XX",
                        "amount": float(record.amount) if record.amount else 0.0,
                        "qty": float(record.qty) if record.qty else 0.0,
                        "date": record.date.isoformat() if record.date else "2024-01-01",
                        "record_id": str(record.id)
                    })
                    indexed += 1
                except Exception as e:
                    print(f"⚠️ Neo4j error for record {record.id}: {e}")
                    self._log_index_error(record, 'neo4j', 'merge_graph', e)

        print(f"✅ Neo4j: created {indexed} graph nodes/relationships")
        return indexed

    def cache_to_redis(self, records: List[Record]):
        """Кешує статистику у Redis"""
        if not records:
            return 0

        # Кешуємо агреговану статистику
        pipeline = self.redis_client.pipeline()
        cached_count = 0

        for record in records:
            # Кеш по HS коду
            if record.hs_code:
                key = f"hs_code:{record.hs_code}:count"
                pipeline.incr(key)
                pipeline.expire(key, 3600)  # 1 година
                cached_count += 1

            # Кеш по компанії
            if record.edrpou:
                key = f"company:{record.edrpou}:total_amount"
                pipeline.incrbyfloat(key, float(record.amount) if record.amount else 0)
                pipeline.expire(key, 3600)
                cached_count += 1 # Count each key update as a cached item

        pipeline.execute()
        print(f"✅ Redis: cached statistics for {cached_count} operations")
        return cached_count

    def close(self):
        """Закриває всі з'єднання"""
        try:
            self.neo4j_driver.close()
            self.redis_client.close()
            print("✅ Closed all database connections")
        except Exception as e:
            print(f"⚠️ Error closing connections: {e}")


def process_excel_file(file_path: str, dataset_name: str, owner: str = "system_user"):
    """
    Обробляє Excel файл та індексує у всі бази даних:
    1. PostgreSQL - структуровані дані
    2. OpenSearch - повнотекстовий пошук
    3. Qdrant - векторний пошук
    4. Neo4j - графові зв'язки
    5. Redis - кеш статистики
    """
    db: Session = SessionLocal()
    indexer = MultiDatabaseIndexer(db_session=db)

    try:
        # Ініціалізуємо індекси/колекції
        print("\n🔧 Initializing database schemas...")
        indexer.ensure_opensearch_index()
        indexer.ensure_qdrant_collection()

        # 1. Create a new Dataset
        print(f"\n📊 Creating dataset: {dataset_name}")
        dataset = Dataset(
            name=dataset_name,
            type="customs",
            description=f"Customs data from {os.path.basename(file_path)}",
            schema_json={},
            owner=owner,
            status="active",
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        print(f"✅ Created Dataset with ID: {dataset.id}")

        # 2. Parse the Excel file
        print("\n📝 Parsing Excel file...")
        parser = ExcelParser()
        parse_result = parser.parse(file_path)
        records_data = parse_result["records"]
        print(f"✅ Parsed {len(records_data)} valid records")

        pg_processed = 0
        pg_failed = 0
        pg_duplicates = 0
        new_records_batch = []

        # 3. Insert parsed records into PostgreSQL
        print("\n💾 Inserting into PostgreSQL...")
        for record_data in records_data:
            try:
                # Check for duplicates based on op_hash
                existing = (
                    db.query(Record).filter(Record.op_hash == record_data.get("op_hash")).first()
                )

                if existing:
                    pg_duplicates += 1
                    continue

                record = Record(
                    dataset_id=dataset.id,
                    pk=record_data["pk"],
                    op_hash=record_data["op_hash"],
                    hs_code=record_data.get("hs_code"),
                    date=record_data.get("date"),
                    amount=record_data.get("amount"),
                    qty=record_data.get("qty"),
                    country_code=record_data.get("country_code"),
                    edrpou=record_data.get("edrpou"),
                    company_name=record_data.get("company_name"),
                    customs_office=record_data.get("customs_office"),
                    attrs=record_data,
                    source_file=os.path.basename(file_path),
                    source_row=int(record_data["pk"].split('_')[-1]),
                )
                db.add(record)
                new_records_batch.append(record)
                pg_processed += 1

                # Commit у батчах по BATCH_SIZE_PG_COMMIT записів
                if len(new_records_batch) >= int(os.getenv("BATCH_SIZE_PG_COMMIT", 1000)):
                    db.commit()
                    print(f"  ✓ Committed batch of {len(new_records_batch)} records to PostgreSQL")
                    new_records_batch = []

            except Exception as e:
                print(f"⚠️ Failed to process record for PostgreSQL: {e}")
                pg_failed += 1

        # Final commit for any remaining records
        if new_records_batch:
            db.commit()
            print(f"  ✓ Final commit: {len(new_records_batch)} records to PostgreSQL")

        # Update dataset metadata
        dataset.row_count = pg_processed
        dataset.updated_at = datetime.now()
        db.commit()

        # 4. Індексуємо у інші бази даних
        print(f"\n🔄 Indexing {pg_processed} records to other databases...")

        # Отримуємо всі нові записи для індексації
        all_records_for_indexing = db.query(Record).filter(Record.dataset_id == dataset.id).all()

        opensearch_indexed_count = 0
        qdrant_upserted_count = 0
        neo4j_indexed_count = 0
        redis_cached_count = 0

        # OpenSearch
        print("\n🔍 Indexing to OpenSearch...")
        opensearch_indexed_count = indexer.index_to_opensearch(all_records_for_indexing)

        # Qdrant
        print("\n🧮 Indexing to Qdrant (vector database)...")
        qdrant_upserted_count = indexer.index_to_qdrant(all_records_for_indexing)

        # Neo4j
        print("\n🕸️ Indexing to Neo4j (graph database)...")
        neo4j_indexed_count = indexer.index_to_neo4j(all_records_for_indexing)

        # Redis
        print("\n⚡ Caching to Redis...")
        redis_cached_count = indexer.cache_to_redis(all_records_for_indexing)

        # Final summary
        print(f"\n{'='*60}")
        print("✅ PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Dataset ID: {dataset.id}")
        print(f"Dataset Name: {dataset.name}")
        print(f"Total rows in Excel: {parse_result['total_rows']}")
        print(f"Valid records parsed: {parse_result['valid_rows']}")
        print(f"Records inserted to PostgreSQL: {pg_processed}")
        print(f"Duplicates skipped (PostgreSQL): {pg_duplicates}")
        print(f"Failed records (PostgreSQL): {pg_failed}")
        print("\n📊 Indexed across all databases:")
        print(f"  ✓ PostgreSQL: {pg_processed} records")
        print(f"  ✓ OpenSearch: {opensearch_indexed_count} records indexed")
        print(f"  ✓ Qdrant: {qdrant_upserted_count} vectors upserted")
        print(f"  ✓ Neo4j: {neo4j_indexed_count} graph nodes/relationships created")
        print(f"  ✓ Redis: {redis_cached_count} statistics cached")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n❌ An error occurred during Excel processing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        indexer.close()
        db.close()

if __name__ == "__main__":
    excel_file_path = "/Users/dima/Desktop/Березень_2024.xlsx"
    dataset_name = "Березень_2024_Customs_Declarations"

    if not os.path.exists(excel_file_path):
        print(f"Error: Excel file not found at {excel_file_path}")
    else:
        process_excel_file(excel_file_path, dataset_name)
