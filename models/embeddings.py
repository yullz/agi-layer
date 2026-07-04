"""Embedding model — text -> vectors for semantic memory.

Tries sentence-transformers (local, fast) first, then an Ollama embeddings
endpoint. Raises if neither is available — the native semantic store catches that
and falls back to a dependency-free hashing embedding, so the layer still runs
offline (weaker vectors, same mechanics). Record the model name on each item so
consolidation can re-embed if you swap models later.
"""
from __future__ import annotations

import json
import urllib.request


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2",
                 endpoint: str = "http://localhost:11434", **opts):
        self.model_name = model_name
        self.endpoint = endpoint.rstrip("/")
        self.opts = opts
        self._model = None
        self._tried = False

    def _load(self):
        if self._tried:
            return self._model
        self._tried = True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except Exception:
            self._model = None
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        if model is not None:
            return [[float(x) for x in v] for v in model.encode(list(texts))]
        return [self._ollama_one(t) for t in texts]  # raises if unreachable

    def _ollama_one(self, text: str) -> list[float]:
        req = urllib.request.Request(
            f"{self.endpoint}/api/embeddings",
            data=json.dumps({"model": self.model_name, "prompt": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))["embedding"]
