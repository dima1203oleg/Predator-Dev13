#!/bin/bash
# Neo4j Constraints Setup Script
# Predator Analytics v13

set -e

echo "🔧 Setting up Neo4j constraints for Predator Analytics..."

# Neo4j connection details
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"

# Cypher commands for constraints
CONSTRAINTS_CYPHER="
CREATE CONSTRAINT company_edrpou IF NOT EXISTS FOR (c:Company) REQUIRE c.edrpou IS UNIQUE;
CREATE CONSTRAINT product_hs_code IF NOT EXISTS FOR (p:Product) REQUIRE p.hs_code IS UNIQUE;
CREATE CONSTRAINT country_code IF NOT EXISTS FOR (co:Country) REQUIRE co.code IS UNIQUE;
"

echo "📋 Applying constraints..."
echo "$CONSTRAINTS_CYPHER" | neo4j-admin database import --verbose neo4j --from=-

# Alternative: using cypher-shell if neo4j-admin not available
# echo "$CONSTRAINTS_CYPHER" | cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI"

echo "✅ Neo4j constraints setup complete!"

# Verification
echo "🔍 Verifying constraints..."
VERIFICATION_CYPHER="
SHOW CONSTRAINTS;
"

echo "$VERIFICATION_CYPHER" | cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI"