# Операційні процедури - Predator Analytics v13

## 🔄 Повний Reindex

### Коли використовувати:
- Після зміни схеми даних
- Після відновлення з backup
- При додаванні нових полів до embeddings
- Для переміщення на нову версію моделі

### Процедура:

```bash
# 1. Підготовка
export DATASET_ID="your-dataset-uuid"

# 2. Очищення цільових БД (опціонально, якщо потрібно повне перестворення)
# OpenSearch: curl -X DELETE "localhost:9200/customs_records"
# Qdrant: видалити колекцію через API
# Neo4j: MATCH (n) DETACH DELETE n
# Redis: FLUSHDB

# 3. Запуск reindex
python3 -c "
from process_excel import MultiDatabaseIndexer
from api.database import SessionLocal
db = SessionLocal()
indexer = MultiDatabaseIndexer(db_session=db)
indexer.reindex_from_postgres('$DATASET_ID')
db.close()
"
```

## 🔍 Перевірка консистентності

### Щоденна перевірка (cron):
```bash
# Додати до crontab: 0 2 * * * /path/to/consistency_check.sh
```

consistency_check.sh:
```bash
#!/bin/bash
DATASET_ID="your-dataset-id"
python3 -c "
from process_excel import MultiDatabaseIndexer
from api.database import SessionLocal
db = SessionLocal()
indexer = MultiDatabaseIndexer(db_session=db)
result = indexer.consistency_check('$DATASET_ID')
if not result['consistent']:
    echo 'INCONSISTENCY DETECTED!' | mail -s 'Predator DB Inconsistency' admin@company.com
db.close()
"
```

### Ручна перевірка:
```python
from process_excel import MultiDatabaseIndexer
from api.database import SessionLocal

db = SessionLocal()
indexer = MultiDatabaseIndexer(db_session=db)
result = indexer.consistency_check("dataset-uuid", sample_size=1000)
print(f"Consistent: {result['consistent']}")
db.close()
```

## 📊 Моніторинг DLQ

### Перегляд помилок:
```sql
SELECT target_db, operation, error_message, created_at
FROM index_errors
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

### Retry failed operations:
```python
from api.database import SessionLocal
from api.models import IndexError

db = SessionLocal()
failed = db.query(IndexError).filter(IndexError.retry_count < 3).all()

for error in failed:
    # Спробувати reindex конкретного запису
    # ... реалізація retry логіки

db.close()
```

## 🚨 Відновлення після збоїв

### OpenSearch failure:
```bash
# Перевірка стану кластера
curl -X GET "localhost:9200/_cluster/health"

# Reindex з PostgreSQL
python3 -c "
from process_excel import MultiDatabaseIndexer
indexer = MultiDatabaseIndexer()
indexer.reindex_from_postgres('dataset-id')
"
```

### Qdrant failure:
```bash
# Перевірка стану
curl -X GET "localhost:6333/health"

# Recreate collection та reindex
python3 -c "
from process_excel import MultiDatabaseIndexer
indexer = MultiDatabaseIndexer()
indexer.ensure_qdrant_collection()
indexer.reindex_from_postgres('dataset-id')
"
```

### Neo4j failure:
```bash
# Перевірка підключення
cypher-shell -u neo4j -p password "MATCH () RETURN count(*)"

# Reindex графу
python3 -c "
from process_excel import MultiDatabaseIndexer
indexer = MultiDatabaseIndexer()
indexer.reindex_from_postgres('dataset-id')
"
```

## 📈 Продуктивність

### Бенчмарки (цільові):
- Embed generation: <60ms per text
- OpenSearch query: <500ms p95
- Qdrant search: <300ms p95
- Batch insert: 1000 records <30s

### Моніторинг:
```python
# Prometheus метрики
from prometheus_client import Counter, Histogram

embed_time = Histogram('predator_embed_duration', 'Embedding generation time')
search_time = Histogram('predator_search_duration', 'Search response time')
index_errors = Counter('predator_index_errors', 'Indexing errors', ['target_db'])
```

## 🔐 Безпека

### PII Masking:
- OpenSearch safe alias: `pa-customs-safe`
- Pipeline: `pii_masking_pipeline`
- Маскування: `edrpou` → `***`, `company_name` → `REDACTED`

### Доступ:
- OpenSearch: basic auth + roles
- Qdrant: network policies
- PostgreSQL: окремі користувачі
- Neo4j: authentication required

## 📋 Backup Strategy

### Повний backup:
1. **PostgreSQL**: `pg_dump` → MinIO
2. **OpenSearch**: Snapshot → MinIO
3. **Qdrant**: Collection snapshot → MinIO
4. **Neo4j**: `neo4j-admin dump` → MinIO
5. **Redis**: RDB snapshot → MinIO

### Automation:
```bash
# Додати до cron: 0 3 * * * /path/to/backup.sh
```

## 🔄 Rolling Updates

### Zero-downtime deployment:
1. Створити новий індекс OpenSearch з новою схемою
2. Переключити alias `pa-customs-read` на новий індекс
3. Видалити старий індекс після 24h
4. Qdrant: створити нову колекцію, переключити після повного reindex
5. Neo4j: rolling update з constraint validation