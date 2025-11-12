#!/bin/bash
# Production Setup Script for Predator Analytics v13
# Initializes all databases and indexes

set -e

echo "🚀 Starting Predator Analytics v13 Production Setup..."

# Load environment variables
if [ -f ".env.production" ]; then
    export $(cat .env.production | xargs)
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 1. Setup PostgreSQL
echo "📊 Setting up PostgreSQL..."
cd api
alembic upgrade head
print_status "PostgreSQL migrations applied"

# 2. Setup Neo4j constraints
echo "🕸️ Setting up Neo4j constraints..."
../scripts/setup_neo4j_constraints.sh

# 3. Setup OpenSearch
echo "🔍 Setting up OpenSearch..."
python3 -c "
from process_excel import MultiDatabaseIndexer
indexer = MultiDatabaseIndexer()
indexer.ensure_opensearch_index()
indexer.setup_opensearch_aliases()
indexer.setup_opensearch_pii_pipeline()
print('OpenSearch setup complete')
"

# 4. Setup Qdrant
echo "🧮 Setting up Qdrant..."
python3 -c "
from process_excel import MultiDatabaseIndexer
indexer = MultiDatabaseIndexer()
indexer.ensure_qdrant_collection()
print('Qdrant setup complete')
"

# 5. Setup Redis (just verify connection)
echo "⚡ Verifying Redis connection..."
python3 -c "
import redis
client = redis.Redis(
    host='${REDIS_HOST:-localhost}',
    port=${REDIS_PORT:-6379},
    decode_responses=True
)
client.ping()
print('Redis connection OK')
"

# 6. Verify Ollama
echo "🤖 Verifying Ollama..."
python3 -c "
import requests
try:
    response = requests.get('${OLLAMA_URL:-http://localhost:11434}/api/tags', timeout=10)
    if response.status_code == 200:
        print('Ollama connection OK')
    else:
        print('Ollama not responding')
except:
    print('Ollama not available - will use fallback embeddings')
"

print_status "Production setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Run your first data import: python process_excel.py"
echo "2. Check consistency: python -c \"from process_excel import MultiDatabaseIndexer; indexer = MultiDatabaseIndexer(); indexer.consistency_check('your-dataset-id')\""
echo "3. Monitor logs for any DLQ entries in PostgreSQL index_errors table"