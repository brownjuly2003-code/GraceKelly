from __future__ import annotations

import hashlib
import json
from threading import Lock
from urllib import request


class EmbeddingsClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.mistral.ai/v1",
        model: str = "mistral-embed",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._cache: dict[str, list[float]] = {}
        self._lock = Lock()

    def embed(self, text: str) -> list[float]:
        if not self._api_key:
            raise RuntimeError("EmbeddingsClient: Mistral API key is not configured.")
        cache_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        embedding = self._fetch_embedding(text)

        with self._lock:
            self._cache[cache_key] = embedding
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            results.append(self.embed(text))
        return results

    def cache_size(self) -> int:
        with self._lock:
            return len(self._cache)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def _fetch_embedding(self, text: str) -> list[float]:
        payload = {
            "model": self._model,
            "input": [text],
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self._base_url}/embeddings",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with request.urlopen(http_request, timeout=self._timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["data"][0]["embedding"]
