from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import pandas as pd
from embeddings import OllamaEmbClient, chunk_text, infer_dim
from opensearchpy import OpenSearch
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from sqlalchemy import create_engine


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def ensure_qdrant_collection(qd: QdrantClient, name: str, dim: int):
    # TODO: Додати обробку винятків за потреби
    info = qd.get_collection(name)
    got = None
    if hasattr(info, "config") and hasattr(info.config, "params"):
        try:
            got = info.config.params.vectors.size
        except Exception:
            got = None
    if got and got != dim:
        qd.recreate_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )


def ensure_os_index(os_client: OpenSearch, index: str):
    if not os_client.indices.exists(index):
        os_client.indices.create(index=index, body={"settings": {"index": {"number_of_shards": 1}}})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--opensearch", required=True)
    ap.add_argument("--qdrant", required=True)
    ap.add_argument("--minio", required=True)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--collection", default="pa_domain_v1")
    ap.add_argument("--index", default="pa-dataset-v1")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "nomic-embed-text"))
    ap.add_argument("--embed-batch", type=int, default=int(os.getenv("EMBED_BATCH", "64")))
    args = ap.parse_args()

    df = pd.read_excel(args.input, engine="openpyxl").fillna("")
    rows: list[dict] = df.to_dict(orient="records")
    if args.verbose:
        print(f"rows={len(rows)}, cols={list(df.columns)}, embed_model={args.embed_model}")

    # PG upsert (опціонально при dry-run)
    eng = create_engine(args.db, pool_pre_ping=True)
    if not args.dry_run:
        with eng.begin() as cx:
            for r in rows:
                payload = json.dumps(r, ensure_ascii=False)
                pk = sha256(payload)
                op_hash = sha256(
                    str(r.get("id", ""))
                    + "|"
                    + str(r.get("date", ""))
                    + "|"
                    + str(r.get("amount", ""))
                )
                cx.exec_driver_sql(
                    "insert into records(pk, op_hash, payload) values(%s,%s,%s) "
                    "on conflict (pk) do update set op_hash=excluded.op_hash, payload=excluded.payload",
                    (pk, op_hash, payload),
                )

    # OpenSearch & Qdrant клієнти
    os_client = OpenSearch(
        hosts=[args.opensearch], http_compress=True, use_ssl=False, verify_certs=False
    )
    ensure_os_index(os_client, args.index)
    qd = QdrantClient(url=args.qdrant, prefer_grpc=False)

    # Підготовка текстів для ембеддингу
    texts = [chunk_text(r) for r in rows]
    if args.dry_run:
        print(f"DRY-RUN: would embed {len(texts)} texts with model={args.embed_model}")
        return

    # Отримуємо ембеддинги з Ollama
    emb_client = OllamaEmbClient(model=args.embed_model)
    # Пробний ембеддинг для визначення розміру
    probe = emb_client.embed_once("probe")
    dim = infer_dim(probe)
    ensure_qdrant_collection(qd, args.collection, dim)

    # Пакетні ембеддинги
    vectors: list[list[float]] = emb_client.embed_list(texts, batch=args.embed_batch)

    # Індексування в OpenSearch (по одному — просто, але надійно)
    for r in rows:
        doc_id = sha256(json.dumps(r, ensure_ascii=False))
        os_client.index(index=args.index, id=doc_id, body=r)

    # Індексування в Qdrant (батчем)
    points = []
    for r, vec in zip(rows, vectors):
        pid = sha256(json.dumps(r, ensure_ascii=False))
        points.append(qm.PointStruct(id=pid, vector=vec, payload=r))
    if points:
        qd.upsert(collection_name=args.collection, points=points)

    print(
        f"OK: indexed PG(+), OS[{args.index}], Qdrant[{args.collection}] with dim={dim}, model={args.embed_model}"
    )


def run_pipeline(
    input_path: str,
    db: str | None,
    opensearch: str | None,
    qdrant: str | None,
    minio: str | None,
    bucket: str,
    embed_model: str = "nomic-embed-text",
    embed_batch: int = 64,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run the full ETL pipeline: parse Excel, upsert to PG, index to OS/Qdrant with Ollama embeddings.
    Returns summary dict.
    """
    # Validate required env vars
    if not db:
        raise ValueError("DB_URL is required")
    if not opensearch:
        raise ValueError("OPENSEARCH_URL is required")
    if not qdrant:
        raise ValueError("QDRANT_URL is required")
    if not minio:
        raise ValueError("MINIO_URL is required")

    df = pd.read_excel(input_path, engine="openpyxl").fillna("")
    rows: list[dict] = df.to_dict(orient="records")
    if verbose:
        print(f"rows={len(rows)}, cols={list(df.columns)}, embed_model={embed_model}")

    result = {
        "rows_parsed": len(rows),
        "pg_upserted": 0,
        "os_indexed": 0,
        "qdrant_indexed": 0,
        "errors": [],
    }

    # PG upsert (опціонально при dry-run)
    if not dry_run:
        try:
            eng = create_engine(db, pool_pre_ping=True)
            with eng.begin() as cx:
                for r in rows:
                    payload = json.dumps(r, ensure_ascii=False)
                    pk = sha256(payload)
                    op_hash = sha256(
                        str(r.get("id", ""))
                        + "|"
                        + str(r.get("date", ""))
                        + "|"
                        + str(r.get("amount", ""))
                    )
                    cx.exec_driver_sql(
                        "insert into records(pk, op_hash, payload) values(%s,%s,%s) "
                        "on conflict (pk) do update set op_hash=excluded.op_hash, payload=excluded.payload",
                        (pk, op_hash, payload),
                    )
            result["pg_upserted"] = len(rows)
        except Exception as e:
            result["errors"].append(f"PG error: {e}")

    # OpenSearch & Qdrant клієнти
    try:
        os_client = OpenSearch(
            hosts=[opensearch], http_compress=True, use_ssl=False, verify_certs=False
        )
        ensure_os_index(os_client, "pa-dataset-v1")
        qd = QdrantClient(url=qdrant, prefer_grpc=False)

        # Підготовка текстів для ембеддингу
        texts = [chunk_text(r) for r in rows]
        if dry_run:
            if verbose:
                print(f"DRY-RUN: would embed {len(texts)} texts with model={embed_model}")
            return result

        # Отримуємо ембеддинги з Ollama
        emb_client = OllamaEmbClient(model=embed_model)
        # Пробний ембеддинг для визначення розміру
        probe = emb_client.embed_once("probe")
        dim = infer_dim(probe)
        ensure_qdrant_collection(qd, "pa_domain_v1", dim)

        # Пакетні ембеддинги
        vectors: list[list[float]] = emb_client.embed_list(texts, batch=embed_batch)

        # Індексування в OpenSearch (по одному — просто, але надійно)
        for r in rows:
            doc_id = sha256(json.dumps(r, ensure_ascii=False))
            os_client.index(index="pa-dataset-v1", id=doc_id, body=r)
        result["os_indexed"] = len(rows)

        # Індексування в Qdrant (батчем)
        points = []
        for r, vec in zip(rows, vectors):
            pid = sha256(json.dumps(r, ensure_ascii=False))
            points.append(qm.PointStruct(id=pid, vector=vec, payload=r))
        if points:
            qd.upsert(collection_name="pa_domain_v1", points=points)
        result["qdrant_indexed"] = len(points)

        if verbose:
            print(
                f"OK: indexed PG(+), OS[pa-dataset-v1], Qdrant[pa_domain_v1] with dim={dim}, model={embed_model}"
            )
        return result
    except Exception as e:
        result["errors"].append(f"Indexing error: {e}")
        return result


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Minimal parse/index CLI skeleton for dry-run and mocks.
This is intentionally lightweight (standard library only) so it runs without installing heavy deps.
Use as a template to wire real parsing and indexing logic.
"""


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Parse an Excel and optionally index to DB / search backends"
    )
    parser.add_argument("--input", required=True, help="Input Excel file path")
    parser.add_argument("--db", help="DB DSN (postgresql://... or sqlite:///file)")
    parser.add_argument("--opensearch", help="OpenSearch endpoint URL")
    parser.add_argument("--index", help="OpenSearch index name")
    parser.add_argument("--qdrant", help="Qdrant endpoint URL")
    parser.add_argument("--collection", help="Qdrant collection name")
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not write to external systems; show actions"
    )
    parser.add_argument(
        "--mock", action="store_true", help="Use internal mocks instead of real clients"
    )

    args = parser.parse_args(argv)

    print(
        f"Inputs:\n  file: {args.input}\n  db: {args.db}\n  opensearch: {args.opensearch}\n  index: {args.index}\n  qdrant: {args.qdrant}\n  collection: {args.collection}"
    )

    if args.dry_run:
        print("\nDry-run mode: no external writes will be performed.")

    if args.mock:
        print("Mock mode: using in-memory mocks for DB and search backends.")

    # Example flow (replace with real parsing + indexing)
    print("\nStep 1: open and validate spreadsheet (simulated)")
    print("  -> would parse rows, validate schema, normalize columns")

    print("\nStep 2: transform to domain records (simulated)")
    print("  -> example record: {'id': 1, 'title': 'Sample', 'score': 0.95}")

    if args.dry_run:
        print("\nStep 3: Dry-run: would send 10 records to DB and search backends (skipped)")
    else:
        print("\nStep 3: Sending to DB and search backends (not implemented in skeleton)")
        print(
            "  -> implement DB client and indexing logic, or run with --mock to use internal mock"
        )

    print("\nFinished (skeleton). Replace functionality with real logic as needed.")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # allow piping/quoting safely
        sys.exit(0)
