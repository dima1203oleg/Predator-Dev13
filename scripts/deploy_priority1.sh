#!/bin/bash
# Deploy Priority 1 Fixes for Predator Analytics v13
# Deploys Neo4j constraints and PostgreSQL DLQ table

set -e  # Exit on error

echo "============================================================"
echo "Predator Analytics v13 - Priority 1 Deployment"
echo "============================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables if .env exists
if [ -f .env ]; then
    echo "📋 Loading .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Default values
NEO4J_URI=${NEO4J_URI:-"bolt://localhost:7687"}
NEO4J_USER=${NEO4J_USER:-"neo4j"}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-"password"}
DATABASE_URL=${DATABASE_URL:-"postgresql://predator:predator_secret@localhost:5432/predator_analytics"}

echo -e "${GREEN}✓${NC} Configuration loaded"
echo ""

# Step 1: Apply PostgreSQL migration
echo "============================================================"
echo "STEP 1: Applying PostgreSQL Migration (DLQ Table)"
echo "============================================================"
echo ""

if [ ! -d "api/alembic" ]; then
    echo -e "${RED}❌ Error: api/alembic directory not found${NC}"
    echo "   Please run this script from the project root directory"
    exit 1
fi

cd api

# Check if alembic is installed
if ! command -v alembic &> /dev/null; then
    echo -e "${YELLOW}⚠️  Alembic not found, attempting to install...${NC}"
    pip install alembic
fi

echo "📦 Running database migration..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ PostgreSQL migration applied successfully${NC}"
else
    echo -e "${RED}❌ PostgreSQL migration failed${NC}"
    exit 1
fi

cd ..
echo ""

# Step 2: Verify DLQ table
echo "============================================================"
echo "STEP 2: Verifying DLQ Table"
echo "============================================================"
echo ""

PSQL_CMD="psql ${DATABASE_URL} -c"

if command -v psql &> /dev/null; then
    echo "🔍 Checking index_errors table..."
    $PSQL_CMD "\d index_errors" > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ index_errors table exists${NC}"
        
        # Show table structure
        echo ""
        echo "📋 Table structure:"
        $PSQL_CMD "\d index_errors"
    else
        echo -e "${YELLOW}⚠️  Could not verify table (psql may not have access)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  psql not found, skipping verification${NC}"
fi

echo ""

# Step 3: Initialize Neo4j constraints
echo "============================================================"
echo "STEP 3: Initializing Neo4j Constraints"
echo "============================================================"
echo ""

if [ ! -f "scripts/init_neo4j_constraints.py" ]; then
    echo -e "${RED}❌ Error: scripts/init_neo4j_constraints.py not found${NC}"
    exit 1
fi

echo "🔧 Creating Neo4j constraints..."
echo "   URI: $NEO4J_URI"
echo "   User: $NEO4J_USER"
echo ""

export NEO4J_URI
export NEO4J_USER
export NEO4J_PASSWORD

python scripts/init_neo4j_constraints.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Neo4j constraints initialized successfully${NC}"
else
    echo ""
    echo -e "${RED}❌ Neo4j constraint initialization failed${NC}"
    echo "   Please check Neo4j connection and credentials"
    exit 1
fi

echo ""

# Final summary
echo "============================================================"
echo "DEPLOYMENT COMPLETE"
echo "============================================================"
echo ""
echo -e "${GREEN}✅ PostgreSQL DLQ table created${NC}"
echo -e "${GREEN}✅ Neo4j constraints initialized${NC}"
echo ""
echo "📊 Next steps:"
echo "   1. Test indexing: python process_excel.py"
echo "   2. Monitor DLQ: SELECT * FROM index_errors;"
echo "   3. Verify Neo4j: SHOW CONSTRAINTS;"
echo ""
echo "📖 Documentation: PRIORITY_1_IMPLEMENTATION.md"
echo "============================================================"
