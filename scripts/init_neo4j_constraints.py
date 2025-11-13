#!/usr/bin/env python3
"""
Neo4j Constraints Initialization Script
Creates UNIQUE constraints for Predator Analytics v13 graph nodes

Usage:
    python scripts/init_neo4j_constraints.py

Environment Variables:
    NEO4J_URI - Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USER - Neo4j username (default: neo4j)
    NEO4J_PASSWORD - Neo4j password (default: password)
"""

import os
import sys

# Use built-in generics (PEP 585) where possible
from neo4j import GraphDatabase


class Neo4jConstraintManager:
    """Manage Neo4j schema constraints"""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print(f"✓ Connected to Neo4j: {uri}")

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()
        print("✓ Closed Neo4j connection")

    def create_constraints(self) -> dict:
        """
        Create all required UNIQUE constraints

        Returns:
            Dict with stats: {created: int, existing: int, failed: int}
        """
        constraints = [
            {
                "name": "unique_company_edrpou",
                "query": "CREATE CONSTRAINT unique_company_edrpou IF NOT EXISTS FOR (c:Company) REQUIRE c.edrpou IS UNIQUE",
                "description": "Company.edrpou UNIQUE constraint",
            },
            {
                "name": "unique_product_hs_code",
                "query": "CREATE CONSTRAINT unique_product_hs_code IF NOT EXISTS FOR (p:Product) REQUIRE p.hs_code IS UNIQUE",
                "description": "Product.hs_code UNIQUE constraint",
            },
            {
                "name": "unique_country_code",
                "query": "CREATE CONSTRAINT unique_country_code IF NOT EXISTS FOR (co:Country) REQUIRE co.code IS UNIQUE",
                "description": "Country.code UNIQUE constraint",
            },
        ]

        stats = {"created": 0, "existing": 0, "failed": 0}

        with self.driver.session() as session:
            # Check existing constraints first
            existing = self._get_existing_constraints(session)
            print(f"\n📋 Found {len(existing)} existing constraints")

            for constraint in constraints:
                try:
                    if constraint["name"] in existing:
                        print(f"⏭️  {constraint['description']} - already exists")
                        stats["existing"] += 1
                    else:
                        session.run(constraint["query"])
                        print(f"✅ {constraint['description']} - created")
                        stats["created"] += 1

                except Exception as e:
                    print(f"❌ {constraint['description']} - failed: {e}")
                    stats["failed"] += 1

        return stats

    def _get_existing_constraints(self, session) -> list[str]:
        """Get list of existing constraint names"""
        result = session.run("SHOW CONSTRAINTS")
        return [record["name"] for record in result if "name" in record]

    def verify_constraints(self) -> bool:
        """
        Verify all constraints are in place

        Returns:
            True if all constraints exist
        """
        required_constraints = [
            "unique_company_edrpou",
            "unique_product_hs_code",
            "unique_country_code",
        ]

        with self.driver.session() as session:
            existing = self._get_existing_constraints(session)

        missing = set(required_constraints) - set(existing)

        if missing:
            print(f"\n⚠️  Missing constraints: {missing}")
            return False
        else:
            print(f"\n✅ All {len(required_constraints)} constraints verified")
            return True

    def create_indexes(self) -> dict:
        """
        Create performance indexes (optional but recommended)

        Returns:
            Dict with stats
        """
        indexes = [
            {
                "name": "idx_company_name",
                "query": "CREATE INDEX idx_company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
                "description": "Company.name index",
            },
            {
                "name": "idx_imports_date",
                "query": "CREATE INDEX idx_imports_date IF NOT EXISTS FOR ()-[r:IMPORTS]-() ON (r.date)",
                "description": "IMPORTS.date relationship index",
            },
            {
                "name": "idx_imports_amount",
                "query": "CREATE INDEX idx_imports_amount IF NOT EXISTS FOR ()-[r:IMPORTS]-() ON (r.amount)",
                "description": "IMPORTS.amount relationship index",
            },
        ]

        stats = {"created": 0, "existing": 0, "failed": 0}

        with self.driver.session() as session:
            existing_indexes = self._get_existing_indexes(session)
            print(f"\n📊 Found {len(existing_indexes)} existing indexes")

            for index in indexes:
                try:
                    if index["name"] in existing_indexes:
                        print(f"⏭️  {index['description']} - already exists")
                        stats["existing"] += 1
                    else:
                        session.run(index["query"])
                        print(f"✅ {index['description']} - created")
                        stats["created"] += 1

                except Exception as e:
                    print(f"❌ {index['description']} - failed: {e}")
                    stats["failed"] += 1

        return stats

    def _get_existing_indexes(self, session) -> list[str]:
        """Get list of existing index names"""
        result = session.run("SHOW INDEXES")
        return [record["name"] for record in result if "name" in record]


def main():
    """Main execution"""
    # Load configuration from environment
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    print("=" * 60)
    print("Neo4j Constraints Initialization")
    print("Predator Analytics v13")
    print("=" * 60)

    try:
        # Initialize manager
        manager = Neo4jConstraintManager(neo4j_uri, neo4j_user, neo4j_password)

        # Create constraints
        print("\n🔧 Creating UNIQUE constraints...")
        constraint_stats = manager.create_constraints()

        # Create indexes (optional)
        print("\n🔧 Creating performance indexes...")
        index_stats = manager.create_indexes()

        # Verify
        print("\n🔍 Verifying constraints...")
        verified = manager.verify_constraints()

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print("Constraints:")
        print(f"  ✓ Created: {constraint_stats['created']}")
        print(f"  ⏭  Existing: {constraint_stats['existing']}")
        print(f"  ❌ Failed: {constraint_stats['failed']}")
        print("\nIndexes:")
        print(f"  ✓ Created: {index_stats['created']}")
        print(f"  ⏭  Existing: {index_stats['existing']}")
        print(f"  ❌ Failed: {index_stats['failed']}")
        print(f"\nVerification: {'✅ PASSED' if verified else '❌ FAILED'}")
        print("=" * 60)

        manager.close()

        # Exit with appropriate code
        sys.exit(0 if verified and constraint_stats["failed"] == 0 else 1)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
