#!/usr/bin/env python3
"""
Neo4j Constraints Setup Script
Predator Analytics v13

Creates unique constraints for Company, Product, and Country nodes
to ensure data integrity in the graph database.

Usage:
    python scripts/setup_neo4j_constraints.py

Environment variables:
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=password
"""

import os
import sys

from neo4j import GraphDatabase


def setup_neo4j_constraints():
    """Create unique constraints for graph nodes"""

    # Configuration
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    constraints = [
        "CREATE CONSTRAINT FOR (c:Company) REQUIRE c.edrpou IS UNIQUE",
        "CREATE CONSTRAINT FOR (p:Product) REQUIRE p.hs_code IS UNIQUE",
        "CREATE CONSTRAINT FOR (co:Country) REQUIRE co.code IS UNIQUE"
    ]

    try:
        with driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    print(f"✅ Created constraint: {constraint}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"✓ Constraint already exists: {constraint}")
                    else:
                        print(f"⚠️ Failed to create constraint: {constraint}")
                        print(f"   Error: {e}")

        print("\n🎯 Neo4j constraints setup completed successfully!")

    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        sys.exit(1)
    finally:
        driver.close()

if __name__ == "__main__":
    setup_neo4j_constraints()
