"""
Retriever Agent: Multi-source data retrieval
- PostgreSQL filter (structured queries)
- Qdrant semantic search (vector similarity)
- OpenSearch full-text search
"""

import logging
import os
from typing import Any

from opensearchpy import OpenSearch
from sqlalchemy import text

from agents.base_agent import AgentContext, BaseAgent
from api.database import get_db
from api.qdrant_manager import QdrantManager

logger = logging.getLogger(__name__)


class RetrieverAgent(BaseAgent):
    """
    Retrieves data from PG, Qdrant, OpenSearch based on query intent

    Strategy:
    1. Parse query → extract filters (hs_code, date range, country, etc.)
    2. PG filter → structured data (fast, precise)
    3. Qdrant → semantic similar (embeddings)
    4. OpenSearch → full-text (company names, text search)
    5. Merge results → ranked by relevance
    """

    def __init__(self, **kwargs):
        super().__init__(name="Retriever", **kwargs)

        # Initialize clients
        self.qdrant = QdrantManager(
            host=os.getenv("QDRANT_HOST", "localhost"),
            collection_name=os.getenv("QDRANT_COLLECTION", "pa_customs_v1"),
        )

        self.opensearch_index = os.getenv(
            "OPENSEARCH_INDEX", "customs_records"
        )  # Changed default index name
        self.opensearch = OpenSearch(
            hosts=[os.getenv("OPENSEARCH_URL", "http://localhost:9200")],
            http_auth=(
                os.getenv("OPENSEARCH_USER", "admin"),
                os.getenv("OPENSEARCH_PASS", "admin"),
            ),
            use_ssl=False,
            verify_certs=False,
        )

        logger.info("RetrieverAgent initialized")

    def _execute_impl(self, context: AgentContext) -> dict[str, Any]:
        """
        Execute retrieval strategy

        Returns:
            {
                "pg_results": [...],
                "qdrant_results": [...],
                "opensearch_results": [...],
                "merged": [...],  # Ranked by relevance
                "total_count": int
            }
        """
        query = context.query

        # Parse query intent (simple keyword extraction)
        filters = self._parse_query(query)

        # 1. PostgreSQL structured filter
        pg_results = self._retrieve_from_pg(filters)

        # 2. Qdrant semantic search (if query has semantic intent)
        qdrant_results = []
        if self._is_semantic_query(query):
            query_vector = self._get_embedding(query)
            qdrant_results = self._retrieve_from_qdrant(query_vector, filters)

        # 3. OpenSearch full-text
        os_results = self._retrieve_from_opensearch(query, filters)

        # 4. Merge and rank
        merged = self._merge_results(pg_results, qdrant_results, os_results)

        return {
            "pg_results": pg_results[:100],  # Limit to 100 per source
            "qdrant_results": qdrant_results[:100],
            "opensearch_results": os_results[:100],
            "merged": merged[:100],  # Top 100 merged
            "total_count": len(merged),
            "filters_applied": filters,
        }

    def _parse_query(self, query: str) -> dict[str, Any]:
        """
        Parse query for structured filters

        Example:
            "Імпорт холодильників 2023 з Китаю" →
            {hs_code: "8418", year: 2023, country: "CHN"}
        """
        filters = {}
        query_lower = query.lower()

        # HS codes (simple pattern matching)
        hs_keywords = {
            "холодильник": "8418",
            "генератор": "8501",
            "автомобіл": "8703",
            "одяг": "61",
            "взуття": "64",
        }
        for keyword, hs_code in hs_keywords.items():
            if keyword in query_lower:
                filters["hs_code"] = hs_code
                break

        # Years (2020-2025)
        import re

        years = re.findall(r"\b(202[0-5])\b", query)
        if years:
            filters["year"] = int(years[0])

        # Countries (simple mapping)
        country_keywords = {
            "китай": "CHN",
            "німеччин": "DEU",
            "польщ": "POL",
            "сша": "USA",
            "туреч": "TUR",
        }
        for keyword, code in country_keywords.items():
            if keyword in query_lower:
                filters["country_code"] = code
                break

        # Amount threshold (>1000000)
        amounts = re.findall(r">\s*(\d+(?:\.\d+)?)\s*(?:млн|мільйон)", query_lower)
        if amounts:
            filters["amount_min"] = float(amounts[0]) * 1_000_000

        logger.debug(f"Parsed filters: {filters}")
        return filters

    def _retrieve_from_pg(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query PostgreSQL with filters"""
        try:
            db = next(get_db())

            # Build WHERE clause
            where_clauses = []
            params = {}

            if "hs_code" in filters:
                where_clauses.append("hs_code LIKE :hs_code")
                params["hs_code"] = f"{filters['hs_code']}%"

            if "year" in filters:
                where_clauses.append("EXTRACT(YEAR FROM date) = :year")
                params["year"] = filters["year"]

            if "country_code" in filters:
                where_clauses.append("country_code = :country_code")
                params["country_code"] = filters["country_code"]

            if "amount_min" in filters:
                where_clauses.append("amount >= :amount_min")
                params["amount_min"] = filters["amount_min"]

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # Query
            sql = f"""
                SELECT pk, hs_code, date, amount, qty, country_code,
                       edrpou, company_name, customs_office
                FROM records
                WHERE {where_sql}
                ORDER BY date DESC
                LIMIT 1000
            """

            result = db.execute(text(sql), params)
            rows = result.fetchall()

            # Convert to dict
            results = []
            for row in rows:
                results.append(
                    {
                        "pk": row[0],
                        "hs_code": row[1],
                        "date": row[2].isoformat() if row[2] else None,
                        "amount": float(row[3]) if row[3] else 0,
                        "qty": row[4],
                        "country_code": row[5],
                        "edrpou": row[6],
                        "company_name": row[7],
                        "customs_office": row[8],
                        "source": "postgresql",
                    }
                )

            logger.info(f"PG: Retrieved {len(results)} records")
            return results

        except Exception as e:
            logger.error(f"PG retrieval failed: {e}")
            return []

    def _is_semantic_query(self, query: str) -> bool:
        """Check if query needs semantic search"""
        semantic_keywords = ["схожі", "подібні", "аналогічні", "як", "типу"]
        return any(kw in query.lower() for kw in semantic_keywords)

    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding from Ollama (nomic-embed-text)"""
        try:
            import requests

            response = requests.post(
                f"{os.getenv('OLLAMA_URL', 'http://localhost:11434')}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=10,
            )

            if response.status_code == 200:
                embedding = response.json().get("embedding", [])
                logger.debug(f"Generated embedding: dim={len(embedding)}")
                return embedding
            else:
                logger.error(f"Embedding failed: {response.status_code}")
                return [0.0] * 768  # Fallback zero vector

        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return [0.0] * 768

    def _retrieve_from_qdrant(
        self, query_vector: list[float], filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Semantic search in Qdrant"""
        try:
            # Convert filters to Qdrant format
            qdrant_filters = {}
            if "hs_code" in filters:
                qdrant_filters["tags"] = filters["hs_code"]

            results = self.qdrant.search_similar(
                query_vector=query_vector, limit=100, score_threshold=0.7, filters=qdrant_filters
            )

            logger.info(f"Qdrant: Retrieved {len(results)} vectors")

            # Format results
            formatted = []
            for hit in results:
                formatted.append(
                    {
                        "pk": hit["payload"]["pk"],
                        "title": hit["payload"]["title"],
                        "tags": hit["payload"]["tags"],
                        "meta": hit["payload"]["meta"],
                        "score": hit["score"],
                        "source": "qdrant",
                    }
                )

            return formatted

        except Exception as e:
            logger.error(f"Qdrant retrieval failed: {e}")
            return []

    def _retrieve_from_opensearch(
        self, query: str, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Full-text search in OpenSearch"""
        try:
            # Build query
            must_clauses = [
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["company_name^2", "hs_code", "customs_office"],
                    }
                }
            ]

            # Add filters
            filter_clauses = []
            if "hs_code" in filters:
                filter_clauses.append({"prefix": {"hs_code": filters["hs_code"]}})

            if "year" in filters:
                filter_clauses.append(
                    {
                        "range": {
                            "date": {
                                "gte": f"{filters['year']}-01-01",
                                "lte": f"{filters['year']}-12-31",
                            }
                        }
                    }
                )

            if "country_code" in filters:
                filter_clauses.append({"term": {"country_code": filters["country_code"]}})

            # Search
            body = {
                "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
                "size": 1000,
                "sort": [{"date": "desc"}],
            }

            response = self.opensearch.search(index=self.opensearch_index, body=body)

            hits = response["hits"]["hits"]
            logger.info(f"OpenSearch: Retrieved {len(hits)} documents")

            # Format results
            results = []
            for hit in hits:
                source = hit["_source"]
                results.append(
                    {
                        "pk": source.get("pk"),
                        "hs_code": source.get("hs_code"),
                        "date": source.get("date"),
                        "amount": source.get("amount"),
                        "company_name": source.get("company_name"),
                        "score": hit["_score"],
                        "source": "opensearch",
                    }
                )

            return results

        except Exception as e:
            logger.error(f"OpenSearch retrieval failed: {e}")
            return []

    def _merge_results(
        self, pg: list[dict], qdrant: list[dict], opensearch: list[dict]
    ) -> list[dict[str, Any]]:
        """
        Merge results from 3 sources, deduplicate by pk, rank by relevance

        Ranking: Qdrant score (semantic) > OpenSearch score (full-text) > PG (exact match)
        """
        merged = {}

        # PG results (base score: 1.0)
        for item in pg:
            pk = item["pk"]
            if pk not in merged:
                merged[pk] = {**item, "relevance_score": 1.0, "sources": ["postgresql"]}

        # Qdrant results (score: 0.7-1.0 semantic)
        for item in qdrant:
            pk = item["pk"]
            score = item.get("score", 0.8)
            if pk in merged:
                merged[pk]["relevance_score"] = max(merged[pk]["relevance_score"], score * 1.2)
                merged[pk]["sources"].append("qdrant")
            else:
                merged[pk] = {**item, "relevance_score": score * 1.2, "sources": ["qdrant"]}

        # OpenSearch results (score: 1.0-10.0 → normalize to 0.8-1.0)
        for item in opensearch:
            pk = item["pk"]
            score = min(item.get("score", 1.0) / 10.0, 1.0) * 0.8
            if pk in merged:
                merged[pk]["relevance_score"] = max(merged[pk]["relevance_score"], score)
                merged[pk]["sources"].append("opensearch")
            else:
                merged[pk] = {**item, "relevance_score": score, "sources": ["opensearch"]}

        # Sort by relevance
        sorted_results = sorted(merged.values(), key=lambda x: x["relevance_score"], reverse=True)

        logger.info(f"Merged {len(sorted_results)} unique records")
        return sorted_results


# ========== TEST ==========
if __name__ == "__main__":
    agent = RetrieverAgent()

    ctx = AgentContext(
        user_id="user_test",
        query="Імпорт холодильників 2023 з Китаю більше 1 млн",
        session_id="session_test",
        trace_id="trace_test",
        access_level="Client",
    )

    result = agent.execute(ctx)
    print(f"Retrieved: {result['total_count']} records")
    print(f"Top 5: {result['merged'][:5]}")
