"""
Qdrant Vector Store Configuration and Management
Predator Analytics v13
"""

import hashlib
import logging
import os
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    UpdateStatus,
    VectorParams,
)

logger = logging.getLogger(__name__)


class QdrantManager:
    """Qdrant vector store manager with idempotent upsert and minimal payload"""

    def __init__(
        self,
        host: str = None,
        port: int = 6333,
        api_key: str = None,
        collection_name: str = "pa_domain_v1",
    ):
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        self.port = port
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name

        # Initialize client
        self.client = QdrantClient(
            host=self.host, port=self.port, api_key=self.api_key, timeout=30
        )

        logger.info(
            f"Qdrant client initialized: {self.host}:{self.port}, collection: {self.collection_name}"
        )

    def create_collection(
        self, vector_size: int = 768, distance: Distance = Distance.COSINE, recreate: bool = False
    ) -> bool:
        """
        Create Qdrant collection with specified vector parameters

        Args:
            vector_size: Embedding dimension (768 for nomic-embed-text, mxbai-embed-large)
            distance: Similarity metric (COSINE default)
            recreate: If True, delete existing collection

        Returns:
            True if created successfully
        """
        try:
            if recreate:
                self.client.delete_collection(self.collection_name)
                logger.info(f"Deleted existing collection: {self.collection_name}")

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=distance),
                optimizers_config={
                    "memmap_threshold": 20000,  # Use memmap for disk-based storage
                    "indexing_threshold": 10000,
                },
                replication_factor=2,
                write_consistency_factor=1,
            )

            logger.info(
                f"Created collection: {self.collection_name}, vector_size={vector_size}, distance={distance}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False

    def upsert_vectors(self, points: list[dict[str, Any]], batch_size: int = 100) -> dict[str, int]:
        """
        Upsert vectors with idempotent operation hash

        Args:
            points: List of dicts with keys: id (pk), vector, payload
                    payload MUST have: pk, title, tags (optional), meta (optional)
                    Additional: op_hash for deduplication
            batch_size: Batch size for upsert

        Returns:
            Dict with stats: {upserted: int, skipped: int, failed: int}
        """
        stats = {"upserted": 0, "skipped": 0, "failed": 0}

        try:
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                qdrant_points = []

                for point in batch:
                    try:
                        pk = point["id"]
                        vector = point["vector"]
                        payload = point.get("payload", {})

                        # Compute op_hash for idempotency
                        op_hash_input = (
                            f"{pk}:{','.join(map(str, vector[:10]))}"  # First 10 dims
                        )
                        op_hash = hashlib.sha256(op_hash_input.encode()).hexdigest()

                        # Minimal payload: pk, title, tags, meta, op_hash
                        minimal_payload = {
                            "pk": pk,
                            "title": payload.get("title", ""),
                            "tags": payload.get("tags", []),
                            "meta": payload.get("meta", {}),
                            "op_hash": op_hash,
                        }

                        qdrant_points.append(
                            PointStruct(
                                id=pk,  # Use business PK as Qdrant ID
                                vector=vector,
                                payload=minimal_payload,
                            )
                        )

                    except Exception as e:
                        logger.error(f"Failed to prepare point {point.get('id')}: {e}")
                        stats["failed"] += 1
                        continue

                # Upsert batch (on_conflict: overwrite)
                if qdrant_points:
                    result = self.client.upsert(
                        collection_name=self.collection_name, points=qdrant_points, wait=True
                    )

                    if result.status == UpdateStatus.COMPLETED:
                        stats["upserted"] += len(qdrant_points)
                        logger.debug(
                            f"Upserted batch {i//batch_size + 1}: {len(qdrant_points)} points"
                        )
                    else:
                        stats["failed"] += len(qdrant_points)
                        logger.error(
                            f"Upsert failed for batch {i//batch_size + 1}: {result.status}"
                        )

            logger.info(f"Upsert completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Upsert operation failed: {e}")
            stats["failed"] += len(points) - stats["upserted"]
            return stats

    def search_similar(
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float = 0.7,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar vectors

        Args:
            query_vector: Query embedding
            limit: Max results
            score_threshold: Minimum similarity score (0.0-1.0)
            filters: Optional filters (e.g., {"tags": "customs"})

        Returns:
            List of dicts: {id, score, payload}
        """
        try:
            # Build filter
            query_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        # Match any in list
                        for v in value:
                            conditions.append(FieldCondition(key=key, match=MatchValue(value=v)))
                    else:
                        conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

                if conditions:
                    query_filter = Filter(should=conditions)

            # Search
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=True,
                with_vectors=False,  # Don't return vectors to save bandwidth
            )

            # Format results
            formatted = []
            for hit in results:
                formatted.append({"id": hit.id, "score": hit.score, "payload": hit.payload})

            logger.debug(f"Search returned {len(formatted)} results (threshold={score_threshold})")
            return formatted

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_collection_info(self) -> dict[str, Any]:
        """Get collection stats"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": info.name,
                "vector_size": info.config.params.vectors.size,
                "distance": info.config.params.vectors.distance,
                "points_count": info.points_count,
                "segments_count": info.segments_count,
                "status": info.status,
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}

    def delete_by_filter(self, filters: dict[str, Any]) -> bool:
        """Delete points matching filter"""
        try:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filters.items()
            ]

            self.client.delete(
                collection_name=self.collection_name, points_selector=Filter(must=conditions)
            )

            logger.info(f"Deleted points matching: {filters}")
            return True

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False


# ========== USAGE EXAMPLE ==========
if __name__ == "__main__":
    # Initialize manager
    manager = QdrantManager(collection_name="pa_customs_v1")

    # Create collection (768-dim vectors, COSINE similarity)
    manager.create_collection(vector_size=768, distance=Distance.COSINE, recreate=False)

    # Upsert sample vectors
    sample_points = [
        {
            "id": "rec_001",
            "vector": [0.1] * 768,  # Replace with actual embeddings
            "payload": {
                "pk": "rec_001",
                "title": "Import генератори 2022",
                "tags": ["customs", "generators"],
                "meta": {"hs_code": "8501", "amount": 1000000},
            },
        }
    ]

    stats = manager.upsert_vectors(sample_points)
    print(f"Upsert stats: {stats}")

    # Search
    query_vector = [0.1] * 768  # Replace with actual query embedding
    results = manager.search_similar(query_vector, limit=5, score_threshold=0.7)
    print(f"Search results: {len(results)}")

    # Collection info
    info = manager.get_collection_info()
    print(f"Collection info: {info}")
