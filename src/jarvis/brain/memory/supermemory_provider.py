"""Supermemory provider (whole-brain integration, Phase A).

:class:`SupermemoryProvider` implements the
:py:class:`~jarvis.brain.memory.provider.MemoryProvider` interface against
a Supermemory server (self-hosted ``supermemory local`` or cloud) using the
v5 HTTP API over stdlib ``urllib`` — no new dependencies.

v5 endpoints used (verified against the live v5 OpenAPI spec):
    add      POST /ns/{namespace}/document            {content, metadata}
    search   POST /ns/{namespace}/search               {query, limit}
    profile  POST /ns/{namespace}/profile
    forget   DELETE /ns/{namespace}/memories/semantic  {query, dryRun}
    list     POST /ns/{namespace}/list/memories        {limit}

Configuration (first match wins):
    1. constructor args
    2. env: JARVIS_SUPERMEMORY_URL, JARVIS_SUPERMEMORY_API_KEY,
       JARVIS_SUPERMEMORY_NAMESPACE
    3. defaults: http://127.0.0.1:6767, no key, namespace "jarvis"

The local self-hosted server prints an API key on first boot; pass it via
JARVIS_SUPERMEMORY_API_KEY (or leave empty — local default needs none).
Timeouts are short (fail fast) so a dead server never stalls a turn.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from jarvis.brain.memory.provider import Memory, MemoryProvider, Profile
from jarvis.brain.memory.write_policy import contains_sensitive

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:6767"
DEFAULT_NAMESPACE = "jarvis"
DEFAULT_TIMEOUT = 3.0


class SupermemoryError(RuntimeError):
    """Raised when the Supermemory server call fails."""


class SupermemoryProvider(MemoryProvider):
    """MemoryProvider backed by a Supermemory v5 HTTP API."""

    name = "supermemory"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        namespace: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("JARVIS_SUPERMEMORY_URL", DEFAULT_URL)
        ).rstrip("/")
        self.api_key = api_key or os.getenv("JARVIS_SUPERMEMORY_API_KEY", "")
        self.namespace = (
            namespace or os.getenv("JARVIS_SUPERMEMORY_NAMESPACE", DEFAULT_NAMESPACE)
        )
        self.timeout = timeout

    # -- low-level HTTP -------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _call(
        self, method: str, path: str, payload: Optional[dict] = None
    ) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310
            url, data=data, headers=self._headers(), method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
                return json.loads(body) if body.strip() else {}
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                detail = ""
            raise SupermemoryError(f"HTTP {e.code} {method} {path}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SupermemoryError(f"unreachable {method} {path}: {e}") from e

    def _ns(self, suffix: str) -> str:
        return f"/ns/{self.namespace}{suffix}"

    # -- MemoryProvider -------------------------------------------------

    def add(self, text: str, metadata: Optional[Dict[str, str]] = None) -> str:
        text = (text or "").strip()
        if not text:
            raise ValueError("empty memory text")
        hit = contains_sensitive(text)
        if hit:
            raise ValueError(hit)
        payload: Dict[str, object] = {"content": text}
        if metadata:
            payload["metadata"] = dict(metadata)
        res = self._call("POST", self._ns("/document"), payload)
        # v5 returns the document id under various keys; be liberal.
        doc_id = (
            res.get("id")
            or res.get("documentId")
            or (res.get("document") or {}).get("id")
            or ""
        )
        logger.debug("supermemory add -> %s", doc_id)
        return str(doc_id)

    def search(self, query: str, limit: int = 5) -> List[Memory]:
        query = (query or "").strip()
        if not query:
            return []
        res = self._call(
            "POST", self._ns("/search"), {"query": query, "limit": limit}
        )
        out: List[Memory] = []
        for item in res.get("results", []) or []:
            mem = item.get("memory") or item
            text = mem.get("content") or mem.get("text") or item.get("content") or ""
            if not text:
                continue
            out.append(
                Memory(
                    id=str(mem.get("id") or item.get("id") or ""),
                    text=text,
                    score=float(item.get("score") or mem.get("score") or 0.0),
                    source="semantic",
                    metadata={
                        k: str(v)
                        for k, v in (mem.get("metadata") or {}).items()
                    },
                )
            )
        return out[:limit]

    def forget(self, query: str) -> int:
        query = (query or "").strip()
        if not query:
            return 0
        # dryRun first so we can report an honest count.
        preview = self._call(
            "DELETE",
            self._ns("/memories/semantic"),
            {"query": query, "dryRun": True},
        )
        doomed = preview.get("memories") or preview.get("results") or []
        count = len(doomed) if isinstance(doomed, list) else int(preview.get("count", 0) or 0)
        self._call(
            "DELETE",
            self._ns("/memories/semantic"),
            {"query": query, "dryRun": False},
        )
        logger.info("supermemory forget %r -> ~%d memories", query, count)
        return count

    def profile(self) -> Profile:
        res = self._call("POST", self._ns("/profile"), {})
        prof = res.get("profile") or res
        summary = prof.get("summary") or prof.get("text") or ""
        facts = prof.get("facts") or prof.get("items") or []
        if isinstance(facts, dict):
            facts = [f"{k}: {v}" for k, v in facts.items()]
        return Profile(
            summary=str(summary),
            facts=[str(f) for f in facts],
            raw=res,
        )

    def health(self) -> bool:
        try:
            # profile is a cheap read; any 2xx means the server is alive.
            self._call("POST", self._ns("/profile"), {})
            return True
        except SupermemoryError as e:
            logger.debug("supermemory health check failed: %s", e)
            return False
        except Exception:
            logger.exception("supermemory health check error")
            return False

    def export(self) -> str:
        res = self._call("POST", self._ns("/list/memories"), {"limit": 200})
        items = res.get("memories") or res.get("results") or res.get("items") or []
        out = [f"# MEMORY EXPORT (supermemory, ns={self.namespace})", "## Memories"]
        for m in items:
            mem = m.get("memory") or m
            text = mem.get("content") or mem.get("text") or str(m)[:200]
            out.append(f"- {text}")
        if len(out) == 2:
            out.append("- (empty)")
        return "\n".join(out)

    def wipe(self) -> None:
        # Forget-everything via a broad semantic query is unreliable; the
        # supported path is deleting the namespace server-side. We surface
        # that as an explicit error so callers can't silently half-wipe.
        raise SupermemoryError(
            "supermemory wipe is not supported via API: delete the namespace "
            f"({self.namespace}) on the server, or forget by topic."
        )
