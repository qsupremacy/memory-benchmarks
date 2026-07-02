"""AWS Bedrock AgentCore Memory — drop-in MemoryBackend for the benchmark.

Mirrors the duck-typed Protocol declared in benchmarks.common.memory_backend:
    async with client as mem0:
        await mem0.add(messages, user_id, timestamp=epoch_seconds)
        await mem0.search(query, user_id, top_k=N, score_debug=False)
        await mem0.get_user_profile(user_id)

`format_search_results()` in mem0_client.py expects each result item to have
`memory` (str), `score` (float), `id` (str). AWS does not expose a numeric
relevance score in its response, so we synthesize a descending-rank score
(1.0, 0.99, 0.98, …) — see the "Open question" note in the plan file. This
is a position proxy, NOT a true relevance signal, so cross-backend
comparisons against this client should treat top-k as the only true
ordering and treat the score column as advisory.

The AWS SDK is synchronous (boto3 / bedrock-agentcore); every call is
wrapped in `asyncio.to_thread()` so the caller can still `await` it from
the same async code paths as Mem0 / AgentArts.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

# Lazy imports: boto3 + bedrock-agentcore are only required when this backend
# is actually selected (so users running Mem0/AgentArts don't need them).
def _import_aws_sdk():
    import boto3
    from bedrock_agentcore.memory import MemorySessionManager
    from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole
    return boto3, MemorySessionManager, ConversationalMessage, MessageRole

# Reuse the Protocol declared in memory_backend.py (kept out of any specific
# backend module so each implementation can be imported without the others'
# SDK dependencies).
from benchmarks.common.memory_backend import MemoryBackend  # noqa: F401  (used as Protocol)

logger = logging.getLogger(__name__)

_boto3 = None
_MemorySessionManager = None
_ConversationalMessage = None
_MessageRole = None


# ---------------------------------------------------------------------------
# Record-shape extractors
# ---------------------------------------------------------------------------
# Bedrock AgentCore Memory's `search_long_term_memories` returns objects whose
# actual payload is wrapped in a `_data` dict (Pydantic v2 raw-shape style).
# We try several known paths so the client tolerates both raw dicts and SDK
# objects, and so schema changes in a future SDK version don't break us.


def _as_dict(rec: Any) -> list[dict[str, Any]]:
    """Return all dict-shaped views of `rec` we can extract."""
    out: list[dict[str, Any]] = []
    if isinstance(rec, dict):
        out.append(rec)
    else:
        try:
            d = rec.__dict__ or {}
            if isinstance(d, dict):
                out.append(d)
        except Exception:  # noqa: BLE001
            pass
        for attr in ("_data", "data"):
            try:
                inner = getattr(rec, attr, None)
            except Exception:  # noqa: BLE001
                inner = None
            if isinstance(inner, dict):
                out.append(inner)
    # Always include the original as a final fallback (non-dict, handled in _extract_text).
    return out


def _extract_text_from_record(rec: Any) -> str:
    """Pull the human-readable text out of a Bedrock memory record.

    Walks several known shapes:
      - dict (raw API response)
      - object with `_data` / `data` attribute holding a dict
      - object with direct `content` / `memory` / `text` attributes
    """
    if rec is None:
        return ""
    for d in _as_dict(rec):
        # Common nested shapes
        for path in (
            ("content", "text"),
            ("_data", "content", "text"),
            ("data", "content", "text"),
        ):
            cur: Any = d
            ok = True
            for k in path:
                if not isinstance(cur, dict) or k not in cur:
                    ok = False
                    break
                cur = cur[k]
            if ok and isinstance(cur, str) and cur.strip():
                return cur
        # Direct string fields
        for key in ("text", "memory", "content"):
            v = d.get(key)
            if isinstance(v, str) and v.strip():
                return v
            if isinstance(v, dict):
                t = v.get("text")
                if isinstance(t, str) and t.strip():
                    return t
    # Last resort: stringify
    return str(rec)


def _extract_id_from_record(rec: Any) -> str | None:
    for d in _as_dict(rec):
        for path in (
            ("id",),
            ("memoryRecordId",),
            ("_data", "memoryRecordId"),
            ("data", "memoryRecordId"),
            ("_data", "id"),
        ):
            cur: Any = d
            ok = True
            for k in path:
                if not isinstance(cur, dict) or k not in cur:
                    ok = False
                    break
                cur = cur[k]
            if ok and isinstance(cur, str) and cur:
                return cur
    return None


def _extract_created_at_from_record(rec: Any) -> str | None:
    for d in _as_dict(rec):
        for path in (
            ("created_at",),
            ("createdAt",),
            ("_data", "createdAt"),
            ("data", "createdAt"),
            ("_data", "created_at"),
        ):
            cur: Any = d
            ok = True
            for k in path:
                if not isinstance(cur, dict) or k not in cur:
                    ok = False
                    break
                cur = cur[k]
            if ok and isinstance(cur, (str, int, float)):
                return str(cur)
    return None


def _extract_score_from_record(rec: Any, default: float) -> Any:
    for d in _as_dict(rec):
        v = d.get("score") or d.get("relevanceScore") or d.get("relevance")
        if v is not None:
            return v
    return default


class AwsAgentCoreMemoryClient:
    """Async wrapper around the synchronous AWS Bedrock AgentCore Memory SDK."""

    def __init__(
        self,
        memory_id: str | None = None,
        region_name: str | None = None,
        session_id: str = "memory-bench-session",
        namespace_path: str = "/",
        max_retries: int = 5,
        retry_delay: float = 5.0,
    ):
        global _boto3, _MemorySessionManager, _ConversationalMessage, _MessageRole
        if _boto3 is None:
            _boto3, _MemorySessionManager, _ConversationalMessage, _MessageRole = _import_aws_sdk()
        region = (
            region_name
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or "ap-southeast-1"
        )
        self._region = region
        resolved = memory_id or os.getenv("AWS_MEMORY_ID") or self._resolve_memory_id(region)
        if not resolved:
            raise ValueError(
                "AWS_MEMORY_ID env var or memory_id argument required "
                "(could not auto-resolve via list_memories)"
            )
        self._memory_id = resolved
        self._session_id = os.getenv("AWS_MEMORY_SESSION_ID", session_id)
        self._namespace_path = os.getenv("AWS_MEMORY_NAMESPACE", namespace_path)
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        self._session_manager = _MemorySessionManager(
            memory_id=self._memory_id, region_name=self._region
        )

        # Per-user session cache, same shape as AgentArtsMemoryClient.
        self._session_cache: dict[str, Any] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._cache_lock = asyncio.Lock()

    @staticmethod
    def _resolve_memory_id(region: str) -> str | None:
        """Best-effort: list existing memories in the account and pick the first one."""
        try:
            client = _boto3.client("bedrock-agentcore-control", region_name=region)
            resp = client.list_memories()
            items = resp.get("memories", []) if isinstance(resp, dict) else []
            return items[0]["id"] if items else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not auto-resolve AWS memory_id via list_memories: %s", exc)
            return None

    async def __aenter__(self) -> "AwsAgentCoreMemoryClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        # boto3 clients are thread-safe and lazy; nothing to close explicitly.
        return None

    async def _get_session(self, actor_id: str) -> Any:
        cached = self._session_cache.get(actor_id)
        if cached:
            return cached
        async with self._cache_lock:
            lock = self._session_locks.setdefault(actor_id, asyncio.Lock())
        async with lock:
            cached = self._session_cache.get(actor_id)
            if cached:
                return cached

            def _create() -> Any:
                return self._session_manager.create_memory_session(
                    actor_id=actor_id,
                    session_id=self._session_id,
                )

            session = await asyncio.to_thread(_create)
            self._session_cache[actor_id] = session
            logger.info(
                "Created AWS memory session actor=%s session=%s",
                actor_id,
                self._session_id,
            )
            return session

    async def _retry(self, fn, op_name: str) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return await asyncio.to_thread(fn)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                delay = self._retry_delay * (2 ** attempt)
                logger.warning(
                    "AWS %s attempt %d/%d failed: %s. Retrying in %.1fs",
                    op_name,
                    attempt + 1,
                    self._max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

    async def add(
        self,
        messages: list[dict[str, Any]],
        user_id: str,
        timestamp: int | None = None,  # noqa: ARG002 — AWS SDK signature in demo does not take ts
        **_unused: Any,
    ) -> dict[str, Any] | None:
        if not messages:
            return {"results": []}

        sdk_msgs: list = []
        for m in messages:
            text = (m.get("content") or "").strip()
            if not text:
                continue
            role_str = str(m.get("role", "user")).upper()
            role = _MessageRole.USER if role_str == "USER" else _MessageRole.ASSISTANT
            sdk_msgs.append(_ConversationalMessage(text, role))

        if not sdk_msgs:
            return {"results": []}

        session = await self._get_session(user_id)

        def _do_add() -> None:
            session.add_turns(messages=sdk_msgs)

        try:
            await self._retry(_do_add, "add_turns")
        except Exception as exc:  # noqa: BLE001
            logger.error("AWS add permanently failed for user_id=%s: %s", user_id, exc)
            return None

        return {
            "results": [
                {
                    "memory": m.text,
                    "event": "ADD",
                    "id": f"aws-{user_id}-{i}",
                }
                for i, m in enumerate(sdk_msgs)
            ]
        }

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 10,
        score_debug: bool = False,  # noqa: ARG002 — accepted for API parity
        **_unused: Any,
    ) -> list[dict[str, Any]]:
        # AWS Bedrock AgentCore Memory caps topK at 100 (ValidationException
        # otherwise). LOCOMO defaults to top_k=200; clamp and warn so the
        # driver can still slice into its 10/20/50/200 cutoffs (200 will
        # equal 100 — same limitation as the AgentArts backend).
        effective_top_k = min(top_k, 100)
        if top_k > 100:
            logger.warning(
                "AWS top_k=%d exceeds backend cap of 100; clamping to 100. "
                "Cutoffs above 100 (e.g. 200) will see no extra results.",
                top_k,
            )
        session = await self._get_session(user_id)

        def _do_search() -> Any:
            return session.search_long_term_memories(
                query=query,
                namespace_path=self._namespace_path,
                top_k=effective_top_k,
            )

        try:
            records = await self._retry(_do_search, "search_long_term_memories")
        except Exception as exc:  # noqa: BLE001
            logger.error("AWS search permanently failed for user_id=%s: %s", user_id, exc)
            return []

        translated: list[dict[str, Any]] = []
        for i, rec in enumerate(records or []):
            text = _extract_text_from_record(rec)
            rec_id = _extract_id_from_record(rec) or f"aws-{user_id}-{i}"
            created_at = _extract_created_at_from_record(rec)
            # NOTE: AWS does not expose a relevance score. Synthesize a
            # descending-rank proxy so search-results objects stay well-formed.
            synthetic = 1.0 - i * 0.01
            try:
                score = float(_extract_score_from_record(rec, synthetic))
            except (TypeError, ValueError):
                score = synthetic
            entry: dict[str, Any] = {
                "memory": str(text),
                "score": score,
                "id": rec_id,
            }
            if created_at:
                entry["created_at"] = created_at
            translated.append(entry)

        translated.sort(key=lambda r: r["score"], reverse=True)
        return translated

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        # Bedrock AgentCore Memory has no first-class "user profile" /
        # reflection concept analogous to AgentArts. We return an empty
        # dict so the call chain stays well-typed; downstream code that
        # expects populated profile data will see the same it sees for any
        # backend with no profile available.
        logger.debug(
            "AWS get_user_profile: not supported by Bedrock AgentCore Memory; returning {}"
        )
        return {}


__all__ = ["AwsAgentCoreMemoryClient"]
