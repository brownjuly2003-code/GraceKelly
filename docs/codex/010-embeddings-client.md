# 010: Embeddings Client — TODO

Phase 6 (Consensus Engine). Dependency: none.
Complexity: moderate | Runs: 2

```
## GOAL
Create a Mistral Embeddings API client with SHA256-based caching. Two new files: `src/gracekelly/core/embeddings.py` and `tests/test_embeddings.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/embeddings.py` — embeddings client with cache
- `tests/test_embeddings.py` — unit tests (mock HTTP, no real API calls)

Files to READ (do NOT modify):
- `src/gracekelly/adapters/api/base.py` — for HTTP pattern reference (uses urllib.request)
- `src/gracekelly/core/consensus.py` — will consume embeddings downstream

Architecture:
- Python >=3.11, no external dependencies (urllib.request for HTTP)
- All files start with `from __future__ import annotations`
- Tests use `unittest.TestCase` with `unittest.mock.patch`
- Test runner: `python -m pytest tests/test_embeddings.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: logging, comments, docstrings, retry logic, or async support.
- HTTP calls use `urllib.request` (NOT httpx, NOT requests). Match the pattern from `base.py`.
- Cache is an in-memory dict keyed by SHA256 of the input text. No file-based cache.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### embeddings.py specification

```python
from __future__ import annotations

import hashlib
import json
from threading import Lock
from urllib import error, request


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
```

That is the COMPLETE implementation. Copy it exactly.

### test_embeddings.py specification

Exactly these tests, using `unittest.mock.patch` to mock `urllib.request.urlopen`:

1. `test_embed_returns_list_of_floats` — mock API response with embedding [0.1, 0.2, 0.3], verify result
2. `test_embed_caches_result` — call embed twice with same text, verify urlopen called only once
3. `test_embed_different_texts_not_cached` — call embed with "a" then "b", verify urlopen called twice
4. `test_embed_batch_returns_list_of_lists` — embed_batch(["a", "b"]) returns list of 2 embeddings
5. `test_cache_size_starts_at_zero` — new client has cache_size() == 0
6. `test_cache_size_after_embed` — after embed("test"), cache_size() == 1
7. `test_clear_cache` — after embed + clear_cache(), cache_size() == 0
8. `test_cache_key_is_sha256` — embed same text, check cache dict key is sha256 hex
9. `test_request_has_bearer_auth` — verify Authorization header is "Bearer <key>"
10. `test_request_posts_to_embeddings_endpoint` — verify URL ends with "/embeddings"
11. `test_request_sends_correct_model` — verify payload contains "model": "mistral-embed"
12. `test_thread_safety` — call embed from 5 threads concurrently, verify no exceptions and cache_size <= 5

Helper for mocking:
```python
def _mock_response(embedding: list[float]):
    response_data = {"data": [{"embedding": embedding}]}
    mock_resp = unittest.mock.MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
    return mock_resp
```

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/embeddings.py` exists with EmbeddingsClient class
- [ ] `tests/test_embeddings.py` exists with exactly 12 test methods
- [ ] `python -m pytest tests/test_embeddings.py -q` → 12 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (541+)
- [ ] No other files created or modified
- [ ] No real API calls in tests (all mocked)

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified?
- Are all 12 tests present with correct mocking?
- Does test_thread_safety actually use threads?
- Is there any code beyond the specification?

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```
