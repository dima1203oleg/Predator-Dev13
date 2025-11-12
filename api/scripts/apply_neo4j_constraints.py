#!/usr/bin/env python3
"""
Apply Neo4j uniqueness constraints idempotently.
This script is intended to be run as a Kubernetes Job (pre-sync hook) from ArgoCD
to ensure required constraints exist before application traffic starts.
"""
import os
import sys
from neo4j import GraphDatabase, basic_auth


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


CONSTRAINTS = [
    # Neo4j 4+ syntax (idempotent with IF NOT EXISTS)
    'CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.edrpou IS UNIQUE',
    'CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.hs_code IS UNIQUE',
    'CREATE CONSTRAINT IF NOT EXISTS FOR (co:Country) REQUIRE co.code IS UNIQUE',
]


def apply_constraints(uri: str, user: str, password: str) -> int:
    driver = None
    applied = 0
    try:
        driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
        with driver.session() as session:
            for c in CONSTRAINTS:
                try:
                    print(f"Applying constraint: {c}")
                    session.run(c)
                    applied += 1
                except Exception as e:
                    # Log and continue; constraint creation is idempotent
                    print(f"Warning: failed to apply constraint '{c}': {e}")
        return applied

    except Exception as e:
        print(f"ERROR: cannot connect to Neo4j at {uri}: {e}")
        return -1
    finally:
        if driver:
            driver.close()


if __name__ == "__main__":
    result = apply_constraints(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    if result == -1:
        print("Failed to apply Neo4j constraints — exiting with error")
        sys.exit(1)
    else:
        print(f"Applied/ensured {result} constraints")
        sys.exit(0)
