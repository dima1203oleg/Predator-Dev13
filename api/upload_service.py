"""
Upload Service: Multi-Database Indexing
Автоматично індексує дані у всі бази даних без дублювання
"""

import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy.orm import Session
from opensearchpy import OpenSearch, helpers as opensearch_helpers
from neo4j import GraphDatabase
import redis

from api.models import Dataset, Record
from api.qdrant_manager import QdrantManager
from parsers.excel_parser import ExcelParser

logger = logging.getLogger(__name__)


class MultiDatabaseUploadService:
    """Сервіс для завантаження та індексації у всі БД"""

    def __init__(self):
        self.stats = {
            "postgresql": 0,
            "opensearch": 0,
            "qdrant": 0,
            "neo4j": 0,
            "redis": 0
        }

    def init_opensearch(self) -> OpenSearch:
        """Ініціалізує з'єднання з OpenSearch"""
        client = OpenSearch(
            hosts=[{
                "host": os.getenv("OPENSEARCH_HOST", "localhost"),
                "port": int(os.getenv("OPENSEARCH_PORT", "9200"))
            }],
            http_auth=(
                os.getenv("OPENSEARCH_USER", "admin"),
                os.getenv("OPENSEARCH_PASSWORD", "admin")
            ),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30
        )

        # Ensure index exists
        if not client.indices.exists(index="customs_records"):
            index_body = {
                "settings": {
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                    "analysis": {
                        "analyzer": {
                            "ukrainian": {
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
                            "analyzer": "ukrainian",
                            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                        },
                        "customs_office": {
                            "type": "text",
                            "analyzer": "ukrainian",
                            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                        },
                        "full_text": {"type": "text", "analyzer": "ukrainian"},
                        "indexed_at": {"type": "date"}
                    }
                }
            }
            client.indices.create(index="customs_records", body=index_body)
            logger.info("✅ Created OpenSearch index: customs_records")

        return client

    def init_qdrant(self) -> QdrantManager:
        """Ініціалізує Qdrant"""
        from qdrant_client.models import Distance

        manager = QdrantManager(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            collection_name="customs_records_v1"
        )

        try:
            manager.create_collection(
                vector_size=768,
                distance=Distance.COSINE,
                recreate=False
            )
            logger.info("✅ Qdrant collection ready")
        except Exception as e:
            logger.warning(f"Qdrant collection exists or error: {e}")

        return manager

    def init_neo4j(self) -> GraphDatabase.driver:
        """Ініціалізує Neo4j"""
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "password")
            )
        )

        # Create indexes
        with driver.session() as session:
            session.run(
                "CREATE INDEX company_edrpou IF NOT EXISTS FOR (c:Company) ON (c.edrpou)"
            )
            session.run(
                "CREATE INDEX product_hs_code IF NOT EXISTS FOR (p:Product) ON (p.hs_code)"
            )
            session.run("CREATE INDEX country_code IF NOT EXISTS FOR (c:Country) ON (c.code)")

        logger.info("✅ Neo4j indexes ensured")
        return driver

    def init_redis(self) -> redis.Redis:
        """Ініціалізує Redis"""
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            decode_responses=True
        )
        client.ping()
        logger.info("✅ Redis connection ready")
        return client

    async def process_upload(
        self,
        file_path: str,
        filename: str,
        dataset_name: str,
        owner: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Головний метод обробки завантаження

        Returns:
            Dict з статистикою обробки
        """
        start_time = time.time()
        result = {
            "success": False,
            "dataset_id": None,
            "records_processed": 0,
            "duplicates": 0,
            "failed": 0,
            "databases_indexed": {},
            "processing_time": 0.0,
            "errors": []
        }

        try:
            # 1. Parse Excel
            logger.info(f"📝 Parsing {filename}...")
            parser = ExcelParser()
            parse_result = parser.parse(file_path)
            records_data = parse_result["records"]
            logger.info(f"✅ Parsed {len(records_data)} valid records")

            # 2. Create Dataset
            dataset = Dataset(
                name=dataset_name,
                type="customs",
                description=f"Customs data from {filename}",
                schema_json={},
                owner=owner,
                status="active"
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)
            result["dataset_id"] = str(dataset.id)
            logger.info(f"✅ Created dataset: {dataset.id}")

            # 3. Insert to PostgreSQL with deduplication
            logger.info("💾 Inserting to PostgreSQL...")
            new_records = []

            for record_data in records_data:
                try:
                    # Check duplicates by op_hash
                    existing = db.query(Record).filter(
                        Record.op_hash == record_data.get("op_hash")
                    ).first()

                    if existing:
                        result["duplicates"] += 1
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
                        source_file=filename,
                        source_row=int(record_data["pk"].split('_')[-1])
                        if '_' in record_data["pk"] else 0
                    )

                    db.add(record)
                    new_records.append(record)
                    result["records_processed"] += 1

                    # Batch commit every 500 records
                    if len(new_records) >= 500:
                        db.commit()
                        logger.info(f"  ✓ Committed batch: {len(new_records)} records")
                        new_records = []

                except Exception as e:
                    logger.error(f"Failed to process record: {e}")
                    result["failed"] += 1

            # Final commit
            if new_records:
                db.commit()
                logger.info(f"  ✓ Final commit: {len(new_records)} records")

            # Update dataset metadata
            dataset.row_count = result["records_processed"]
            dataset.updated_at = datetime.now()
            db.commit()

            self.stats["postgresql"] = result["records_processed"]
            result["databases_indexed"]["postgresql"] = result["records_processed"]

            # 4. Get all records for indexing to other DBs
            all_records = db.query(Record).filter(Record.dataset_id == dataset.id).all()

            # 5. Index to OpenSearch
            try:
                logger.info("🔍 Indexing to OpenSearch...")
                opensearch = self.init_opensearch()
                indexed = await self.index_to_opensearch(opensearch, all_records)
                self.stats["opensearch"] = indexed
                result["databases_indexed"]["opensearch"] = indexed
            except Exception as e:
                logger.error(f"OpenSearch indexing failed: {e}")
                result["errors"].append(f"OpenSearch: {str(e)}")

            # 6. Index to Qdrant (векторний пошук)
            try:
                logger.info("🧮 Indexing to Qdrant...")
                qdrant = self.init_qdrant()
                indexed = await self.index_to_qdrant(qdrant, all_records)
                self.stats["qdrant"] = indexed
                result["databases_indexed"]["qdrant"] = indexed
            except Exception as e:
                logger.error(f"Qdrant indexing failed: {e}")
                result["errors"].append(f"Qdrant: {str(e)}")

            # 7. Index to Neo4j (графові зв'язки)
            try:
                logger.info("🕸️ Indexing to Neo4j...")
                neo4j = self.init_neo4j()
                indexed = await self.index_to_neo4j(neo4j, all_records)
                neo4j.close()
                self.stats["neo4j"] = indexed
                result["databases_indexed"]["neo4j"] = indexed
            except Exception as e:
                logger.error(f"Neo4j indexing failed: {e}")
                result["errors"].append(f"Neo4j: {str(e)}")

            # 8. Cache to Redis
            try:
                logger.info("⚡ Caching to Redis...")
                redis_client = self.init_redis()
                cached = await self.cache_to_redis(redis_client, all_records)
                redis_client.close()
                self.stats["redis"] = cached
                result["databases_indexed"]["redis"] = cached
            except Exception as e:
                logger.error(f"Redis caching failed: {e}")
                result["errors"].append(f"Redis: {str(e)}")

            result["success"] = True
            result["processing_time"] = time.time() - start_time

            logger.info(f"✅ Upload completed in {result['processing_time']:.2f}s")
            logger.info(f"📊 Stats: {self.stats}")

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            result["errors"].append(str(e))
            import traceback
            traceback.print_exc()

        return result

    async def index_to_opensearch(self, client: OpenSearch, records: List[Record]) -> int:
        """Індексує записи у OpenSearch"""
        if not records:
            return 0

        actions = []
        for record in records:
            # Повнотекстовий контент для пошуку
            full_text = " ".join(filter(None, [
                record.company_name,
                record.hs_code,
                record.customs_office,
                record.edrpou,
                record.country_code
            ]))

            action = {
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
            actions.append(action)

        success, errors = opensearch_helpers.bulk(client, actions, raise_on_error=False)
        logger.info(f"✅ OpenSearch: indexed {success} records")

        if errors:
            logger.warning(f"⚠️ OpenSearch: {len(errors)} errors")

        return success

    async def index_to_qdrant(self, manager: QdrantManager, records: List[Record]) -> int:
        """Індексує записи у Qdrant (векторний пошук)"""
        if not records:
            return 0

        # TODO: Integrate with Ollama for real embeddings
        # For now, skip or use placeholder
        logger.info("⚠️ Qdrant indexing requires Ollama embeddings - skipped for now")
        return 0

    async def index_to_neo4j(self, driver, records: List[Record]) -> int:
        """Індексує записи у Neo4j (графові зв'язки)"""
        if not records:
            return 0

        indexed = 0
        batch_size = 100

        with driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]

                for record in batch:
                    try:
                        session.run("""
                            MERGE (c:Company {edrpou: $edrpou})
                            ON CREATE SET c.name = $company_name
                            ON MATCH SET c.name = $company_name

                            MERGE (p:Product {hs_code: $hs_code})

                            MERGE (co:Country {code: $country_code})

                            MERGE (c)-[r:IMPORTS {record_id: $record_id}]->(p)
                            SET r.amount = $amount,
                                r.qty = $qty,
                                r.date = date($date)

                            MERGE (p)-[:FROM_COUNTRY]->(co)
                        """, {
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
                        logger.error(f"Neo4j error for record {record.id}: {e}")

                if (i + batch_size) % 1000 == 0:
                    logger.info(f"  ✓ Neo4j: processed {i + batch_size} records")

        logger.info(f"✅ Neo4j: indexed {indexed} graph relationships")
        return indexed

    async def cache_to_redis(self, client: redis.Redis, records: List[Record]) -> int:
        """Кешує статистику у Redis"""
        if not records:
            return 0

        cached = 0
        pipeline = client.pipeline()

        for record in records:
            try:
                # Кеш по HS коду
                if record.hs_code:
                    key = f"hs_code:{record.hs_code}:count"
                    pipeline.incr(key)
                    pipeline.expire(key, 3600)  # 1 година

                # Кеш по компанії
                if record.edrpou:
                    key = f"company:{record.edrpou}:total_amount"
                    pipeline.incrbyfloat(key, float(record.amount) if record.amount else 0)
                    pipeline.expire(key, 3600)

                # Кеш по країні
                if record.country_code:
                    key = f"country:{record.country_code}:count"
                    pipeline.incr(key)
                    pipeline.expire(key, 3600)

                cached += 1
            except Exception as e:
                logger.error(f"Redis caching error for record {record.id}: {e}")

        pipeline.execute()
        logger.info(f"✅ Redis: cached {cached} statistics")
        return cached
