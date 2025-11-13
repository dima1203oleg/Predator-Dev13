from __future__ import annotations

import os

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


class OllamaEmbClient:
    def __init__(
        self, base_url: str | None = None, model: str | None = None, timeout: float = 60.0
    ):
        self.base_url = base_url or OLLAMA_URL
        self.model = model or EMBED_MODEL
        self.timeout = timeout
        self._http = httpx.Client(timeout=self.timeout)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def embed_once(self, text: str) -> list[float]:
        r = self._http.post(
            f"{self.base_url}/api/embeddings", json={"model": self.model, "prompt": text}
        )
        r.raise_for_status()
        data = r.json()
        # Ollama responses may vary; try common keys
        emb = data.get("embedding") or data.get("data") or []
        if isinstance(emb, list) and emb and isinstance(emb[0], (int, float)):
            return emb
        # If response nested
        if isinstance(emb, list) and emb and isinstance(emb[0], dict):
            return emb[0].get("embedding", [])
        raise RuntimeError(f"Ollama empty or unexpected embedding for model={self.model}")

    def embed_list(self, texts: list[str], batch: int = 64) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), batch):
            chunk = texts[i : i + batch]
            for t in chunk:
                out.append(self.embed_once(t))
        return out

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def tags(self) -> dict:
        r = self._http.get(f"{self.base_url}/api/tags")
        r.raise_for_status()
        return r.json()


def infer_dim(embedding: list[float]) -> int:
    return len(embedding)


def chunk_text(record: dict, max_len: int = 2000) -> str:
    vals = [str(v) for v in record.values()]
    text = " ".join(vals)
    if len(text) > max_len:
        return text[:max_len]
    return text
