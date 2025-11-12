#!/bin/bash
# Initialize Neo4j constraints for Predator Analytics v13
# Usage: ./scripts/init_neo4j.sh [NEO4J_URI] [NEO4J_USER] [NEO4J_PASSWORD]

set -e

# Configuration from environment or arguments
NEO4J_URI=${1:-${NEO4J_URI:-"bolt://localhost:7687"}}
NEO4J_USER=${2:-${NEO4J_USER:-"neo4j"}}
NEO4J_PASSWORD=${3:-${NEO4J_PASSWORD:-"password"}}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CYPHER_FILE="${SCRIPT_DIR}/init_neo4j_constraints.cypher"

echo "🔧 Initializing Neo4j constraints..."
echo "   URI: ${NEO4J_URI}"
echo "   User: ${NEO4J_USER}"

# Check if cypher-shell is available
if ! command -v cypher-shell &> /dev/null; then
    echo "❌ Error: cypher-shell not found. Install Neo4j or add it to PATH."
    echo "   Alternative: Use Neo4j Browser at http://localhost:7474"
    exit 1
fi

# Execute constraints script
echo "📝 Applying constraints from ${CYPHER_FILE}..."
cypher-shell -a "${NEO4J_URI}" -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" < "${CYPHER_FILE}"

if [ $? -eq 0 ]; then
    echo "✅ Neo4j constraints successfully created!"
    
    # Verify constraints
    echo ""
    echo "📊 Verifying constraints..."
    cypher-shell -a "${NEO4J_URI}" -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" \
        "SHOW CONSTRAINTS;"
else
    echo "❌ Failed to create Neo4j constraints"
    exit 1
fi

echo ""
echo "✅ Neo4j initialization complete!"
