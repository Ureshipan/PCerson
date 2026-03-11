from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable


class VectorMemoryStore:
    def __init__(self, models_config: dict[str, Any]) -> None:
        self.config = models_config.get("memory", {})
        self.enabled = bool(self.config.get("enabled", False))
        self.backend = str(self.config.get("backend", "none")).lower()
        self.endpoint = str(self.config.get("endpoint", "http://127.0.0.1:6333")).rstrip("/")
        self.collection = str(self.config.get("collection", "assistant_memory"))
        self.top_k = int(self.config.get("top_k", 6))
        self._collection_ready = False

    def healthcheck(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "backend": self.backend, "ok": True}
        if self.backend != "qdrant":
            return {"enabled": True, "backend": self.backend, "ok": False, "error": "Unsupported backend"}
        try:
            response = self._request("GET", f"/collections/{urllib.parse.quote(self.collection)}")
            result = response.get("result", {})
            points_count = result.get("points_count")
            return {
                "enabled": True,
                "backend": "qdrant",
                "ok": True,
                "collection": self.collection,
                "points_count": points_count,
            }
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return {
                    "enabled": True,
                    "backend": "qdrant",
                    "ok": True,
                    "collection": self.collection,
                    "collection_exists": False,
                    "points_count": 0,
                }
            return {"enabled": True, "backend": "qdrant", "ok": False, "error": str(exc)}
        except Exception as exc:  # pragma: no cover
            return {"enabled": True, "backend": "qdrant", "ok": False, "error": str(exc)}

    def upsert_text_memories(
        self,
        items: list[dict[str, Any]],
        embed_texts: Callable[[list[str]], list[list[float]]],
    ) -> None:
        if not self.enabled or self.backend != "qdrant" or not items:
            return
        texts = [str(item.get("text", "")).strip() for item in items]
        texts = [text for text in texts if text]
        if not texts:
            return
        vectors = embed_texts(texts)
        if not vectors:
            return
        try:
            self._ensure_collection(len(vectors[0]))
        except Exception:
            return
        points = []
        for item, vector in zip(items, vectors):
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            point_id = item.get("id") or self._stable_id(str(item.get("kind", "memory")), text)
            points.append(
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "kind": str(item.get("kind", "memory")),
                        "text": text,
                        "created_at": item.get("created_at", ""),
                        "source": item.get("source", "assistant"),
                        "metadata": item.get("metadata", {}),
                    },
                }
            )
        if not points:
            return
        try:
            self._request(
                "PUT",
                f"/collections/{urllib.parse.quote(self.collection)}/points?wait=true",
                {"points": points},
            )
        except Exception:
            return

    def search(
        self,
        query: str,
        embed_texts: Callable[[list[str]], list[list[float]]],
        limit: int | None = None,
        kinds: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled or self.backend != "qdrant":
            return []
        query = query.strip()
        if not query:
            return []
        vectors = embed_texts([query])
        if not vectors:
            return []
        try:
            self._ensure_collection(len(vectors[0]))
        except Exception:
            return []
        payload: dict[str, Any] = {
            "query": vectors[0],
            "limit": int(limit or self.top_k),
            "with_payload": True,
        }
        if kinds:
            payload["filter"] = {
                "must": [
                    {
                        "key": "kind",
                        "match": {"any": kinds},
                    }
                ]
            }
        try:
            response = self._request(
                "POST",
                f"/collections/{urllib.parse.quote(self.collection)}/points/query",
                payload,
            )
            result = response.get("result", {})
            points = result.get("points", [])
        except Exception:
            try:
                response = self._request(
                    "POST",
                    f"/collections/{urllib.parse.quote(self.collection)}/points/search",
                    {
                        "vector": vectors[0],
                        "limit": int(limit or self.top_k),
                        "with_payload": True,
                        **({"filter": payload["filter"]} if "filter" in payload else {}),
                    },
                )
                points = response.get("result", [])
            except Exception:
                return []

        memories: list[dict[str, Any]] = []
        for point in points:
            payload_item = point.get("payload", {})
            if not isinstance(payload_item, dict):
                continue
            memories.append(
                {
                    "id": point.get("id"),
                    "score": point.get("score"),
                    "kind": payload_item.get("kind"),
                    "text": payload_item.get("text"),
                    "created_at": payload_item.get("created_at"),
                    "metadata": payload_item.get("metadata", {}),
                }
            )
        return memories

    def _ensure_collection(self, vector_size: int) -> None:
        if self._collection_ready:
            return
        collection_path = f"/collections/{urllib.parse.quote(self.collection)}"
        try:
            self._request("GET", collection_path)
        except Exception:
            try:
                self._request(
                    "PUT",
                    collection_path,
                    {"vectors": {"size": vector_size, "distance": "Cosine"}},
                )
            except RuntimeError as exc:
                if "HTTP 409" not in str(exc):
                    raise
        self._collection_ready = True

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(f"{self.endpoint}{path}", method=method, data=body, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:  # pragma: no cover
            details = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Qdrant HTTP {exc.code}: {details or exc.reason}") from exc

    def _stable_id(self, kind: str, text: str) -> str:
        digest = hashlib.sha1(f"{kind}:{text.strip().lower()}".encode("utf-8")).hexdigest()
        return str(uuid.uuid5(uuid.NAMESPACE_URL, digest))
