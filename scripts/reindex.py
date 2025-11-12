import argparse
import json

from opensearchpy import OpenSearch
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from sqlalchemy import create_engine, text


def main():
  p = argparse.ArgumentParser()
  p.add_argument("--db", required=True)
  p.add_argument("--opensearch", required=True)
  p.add_argument("--qdrant", required=True)
  p.add_argument("--index", default="pa-dataset-v1")
  p.add_argument("--collection", default="pa_domain_v1")
  a = p.parse_args()

  eng = create_engine(a.db, pool_pre_ping=True)
  os = OpenSearch(hosts=[a.opensearch], http_compress=True, use_ssl=False, verify_certs=False)
  qd = QdrantClient(url=a.qdrant, prefer_grpc=False)

  # простий повний реіндекс (демо)
  rows = []
  with eng.begin() as cx:
    res = cx.execute(text("select pk, payload from records"))
    for pk, payload in res:
      rows.append((pk, json.loads(payload)))

  # OS reindex
  for pk, payload in rows:
    os.index(index=a.index, id=pk, body=payload)

  # Qdrant reindex (з фейк-вектором)
  def fake_embed(text: str):
    import hashlib
    h = hashlib.sha256(text.encode()).hexdigest()
    v = [int(h[i:i+2],16)/255.0 for i in range(0, 64, 2)]
    return (v*48)[:768]

  pts = []
  for pk, payload in rows:
    text = " ".join([str(v) for v in payload.values()])[:2000]
    pts.append(qm.PointStruct(id=pk, vector=fake_embed(text), payload=payload))
  if pts:
    qd.upsert(collection_name=a.collection, points=pts)

  print(f"reindex: OK ({len(rows)} docs)")

if __name__ == "__main__":
  main()
