import argparse

import requests
from sqlalchemy import create_engine


def main():
  p = argparse.ArgumentParser()
  p.add_argument("--db", required=True)
  p.add_argument("--opensearch", required=True)
  p.add_argument("--qdrant", required=True)
  p.add_argument("--minio", required=True)
  p.add_argument("--ollama", default="http://localhost:11434")
  a = p.parse_args()

  create_engine(a.db).connect().close()
  assert requests.get(a.opensearch).ok, "OpenSearch not OK"
  assert requests.get(f"{a.qdrant}/collections").ok, "Qdrant not OK"
  assert requests.get(a.minio).ok, "MinIO not OK"
  rt = requests.get(f"{a.ollama}/api/tags")
  assert rt.ok, "Ollama not OK"
  print("health: OK")

if __name__ == "__main__":
  main()
