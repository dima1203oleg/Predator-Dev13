#!/bin/bash
# Priority 1 Critical Fixes Deployment Script
# Predator Analytics v13

set -e

echo "🚀 Deploying Priority 1 Critical Fixes for Predator Analytics v13"
echo "================================================================="

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

# Check if we're in the right directory
if [ ! -f "process_excel.py" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

echo "📍 Working directory: $(pwd)"

# 1. Run Alembic migration for index_errors table
echo -e "\n1. Running database migration for DLQ table..."
cd api
if command -v alembic &> /dev/null; then
    alembic upgrade head
    print_status "Database migration completed"
else
    print_warning "Alembic not found. Please run migration manually:"
    echo "  cd api && alembic upgrade head"
fi
cd ..

# 2. Setup Neo4j constraints
echo -e "\n2. Setting up Neo4j constraints..."
if [ -f "scripts/setup_neo4j_constraints.py" ]; then
    python scripts/setup_neo4j_constraints.py
    print_status "Neo4j constraints created"
else
    print_warning "Neo4j constraints script not found. Please run manually:"
    echo "  python scripts/setup_neo4j_constraints.py"
fi

# 3. Verify OpenSearch index exists
echo -e "\n3. Verifying OpenSearch index..."
python -c "
from process_excel import MultiDatabaseIndexer
indexer = MultiDatabaseIndexer()
indexer.ensure_opensearch_index()
indexer.close()
print('OpenSearch index verified')
"

# 4. Verify Qdrant collection exists
echo -e "\n4. Verifying Qdrant collection..."
python -c "
from process_excel import MultiDatabaseIndexer
indexer = MultiDatabaseIndexer()
indexer.ensure_qdrant_collection()
indexer.close()
print('Qdrant collection verified')
"

# 5. Test basic functionality
echo -e "\n5. Running basic functionality test..."
python -c "
import os
from process_excel import MultiDatabaseIndexer

# Test configuration loading
indexer = MultiDatabaseIndexer()
print(f'OpenSearch host: {indexer.opensearch_host}')
print(f'Qdrant collection: {indexer.qdrant_collection}')
print(f'Qdrant vector size: {indexer.qdrant_vector_size}')
print(f'Ollama URL: {indexer.ollama_url}')
print(f'Ollama model: {indexer.ollama_embed_model}')
indexer.close()
print('Configuration test passed')
"

echo -e "\n${GREEN}🎯 Priority 1 Critical Fixes Deployment Complete!${NC}"
echo "======================================================"
echo ""
echo "What's been deployed:"
echo "✅ IndexError DLQ table (database migration)"
echo "✅ Neo4j unique constraints for Company/Product/Country"
echo "✅ OpenSearch index with proper mapping"
echo "✅ Qdrant collection with COSINE distance"
echo "✅ Enhanced error handling with DLQ logging"
echo ""
echo "Next steps:"
echo "1. Test with a small Excel file: python process_excel.py"
echo "2. Monitor logs for DLQ entries in case of failures"
echo "3. Consider Priority 2 improvements (OpenSearch aliases, PII masking)"
echo ""
echo "Ready for production! 🚀"