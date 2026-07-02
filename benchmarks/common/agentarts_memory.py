"""Drop-in replacement for Mem0Client backed by the HuaweiCloud AgentArts Memory SDK.

Mirrors the surface used by benchmarks/locomo/run.py:
    async with client as mem0:
        await mem0.add(messages, user_id, timestamp=epoch_seconds)
        await mem0.search(query, user_id, top_k=N, score_debug=False)
        await mem0.get_user_profile(user_id)

`format_search_results()` in mem0_client.py expects each result item to have
`memory` (str), `score` (float), `id` (str). AgentArts returns
`{"record": text, "score": float}` pairs from `search_memories`, so we translate
here. Sort order is descending by score, matching the contract.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

from agentarts.sdk.memory import AsyncMemoryClient
from agentarts.sdk.memory.inner.config import (
    MemoryListFilter,
    MemorySearchFilter,
    TextMessage,
)

logger = logging.getLogger(__name__)


class MemoryBackend(Protocol):
    """Duck-typed surface used by benchmarks. Both Mem0Client and AgentArtsMemoryClient satisfy this."""

    async def add(self, messages: list[dict[str, Any]], user_id: str, timestamp: int | None = ...) -> dict[str, Any] | None: ...
    async def search(self, query: str, user_id: str, top_k: int = ..., score_debug: bool = ...) -> list[dict[str, Any]]: ...
    async def get_user_profile(self, user_id: str) -> dict[str, Any]: ...
    async def close(self) -> None: ...
    async def __aenter__(self) -> "MemoryBackend": ...
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...


class AgentArtsMemoryClient:
    def __init__(
        self,
        api_key: str,
        space_id: str,
        region: str = "cn-southwest-2",
        max_retries: int = 5,
        retry_delay: float = 5.0,
    ):
        if not api_key:
            raise ValueError("api_key is required for AgentArtsMemoryClient")
        if not space_id:
            raise ValueError("space_id is required for AgentArtsMemoryClient")

        self._client = AsyncMemoryClient(api_key=api_key, region_name=region)
        self._space_id = space_id
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        self._session_cache: dict[str, str] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._cache_lock = asyncio.Lock()

    async def __aenter__(self) -> "AgentArtsMemoryClient":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._client.__aexit__(exc_type, exc_val, exc_tb)

    async def close(self) -> None:
        await self._client.close()

    async def _get_session_id(self, user_id: str) -> str:
        cached = self._session_cache.get(user_id)
        if cached:
            return cached

        async with self._cache_lock:
            lock = self._session_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            cached = self._session_cache.get(user_id)
            if cached:
                return cached
            session = await self._client.create_memory_session(
                space_id=self._space_id, actor_id=user_id
            )
            self._session_cache[user_id] = session.id
            logger.info("Created AgentArts session %s for user_id=%s", session.id, user_id)
            return session.id

    async def _retry(self, coro_factory, op_name: str) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return await coro_factory()
            except Exception as exc:  # noqa: BLE001 — surface any SDK/HTTP error uniformly
                last_exc = exc
                delay = self._retry_delay * (2 ** attempt)
                logger.warning(
                    "AgentArts %s failed (attempt %d/%d): %s. Retrying in %.1fs",
                    op_name, attempt + 1, self._max_retries, exc, delay,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

    async def add(
        self,
        messages: list[dict[str, Any]],
        user_id: str,
        timestamp: int | None = None,
        **_unused: Any,
    ) -> dict[str, Any] | None:
        if not messages:
            return {"results": []}

        session_id = await self._get_session_id(user_id)

        sdk_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content.strip():
                continue
            sdk_messages.append(TextMessage(role=role, content=content, actor_id=user_id))

        if not sdk_messages:
            return {"results": []}

        ts_ms = int(timestamp * 1000) if timestamp is not None else None

        async def _do_add() -> Any:
            return await self._client.add_messages(
                space_id=self._space_id,
                session_id=session_id,
                messages=sdk_messages,
                timestamp=ts_ms,
            )

        try:
            batch_resp = await self._retry(_do_add, "add_messages")
        except Exception as exc:  # noqa: BLE001
            logger.error("AgentArts add permanently failed for user_id=%s: %s", user_id, exc)
            return None

        results = []
        if batch_resp is not None:
            msg_items = getattr(batch_resp, "items", None) or []
            for i, item in enumerate(msg_items):
                item_dict = item if isinstance(item, dict) else item.__dict__
                content = (
                    item_dict.get("content")
                    or item_dict.get("text")
                    or (sdk_messages[i].content if i < len(sdk_messages) else "")
                )
                results.append({
                    "memory": content,
                    "event": "ADD",
                    "id": item_dict.get("id", f"msg-{i}"),
                })

        return {"results": results}

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 10,
        score_debug: bool = False,  # noqa: ARG002 — accepted for API parity; no AgentArts equivalent
        **_unused: Any,
    ) -> list[dict[str, Any]]:
        # AgentArts API caps topK at 100. LOCOMO defaults to top_k=200; clamp and warn
        # so the driver can still slice into its 10/20/50/200 cutoffs (200 will equal 100).
        effective_top_k = min(top_k, 100)
        if top_k > 100:
            logger.warning(
                "AgentArts top_k=%d exceeds backend cap of 100; clamping to 100. "
                "Cutoffs above 100 (e.g. 200) will see no extra results.",
                top_k,
            )
        flt = MemorySearchFilter(query=query, actor_id=user_id, top_k=effective_top_k)

        async def _do_search() -> Any:
            return await self._client.search_memories(
                space_id=self._space_id, filters=flt
            )

        try:
            resp = await self._retry(_do_search, "search_memories")
        except Exception as exc:  # noqa: BLE001
            logger.error("AgentArts search permanently failed for user_id=%s: %s", user_id, exc)
            return []

        raw_results = getattr(resp, "results", None) or []
        translated: list[dict[str, Any]] = []
        for i, item in enumerate(raw_results):
            if not isinstance(item, dict):
                item = item.__dict__ if hasattr(item, "__dict__") else {}
            text = item.get("record") or item.get("memory") or ""
            score = item.get("score", 0.0)
            translated.append({
                "memory": text,
                "score": float(score) if score is not None else 0.0,
                "id": item.get("id") or f"agentarts-{user_id}-{i}",
            })

        translated.sort(key=lambda r: r["score"], reverse=True)
        return translated

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        flt = MemoryListFilter(actor_id=user_id, memory_type="reflection")

        async def _do_list() -> Any:
            return await self._client.list_memories(
                space_id=self._space_id, limit=50, offset=0, filters=flt
            )

        try:
            resp = await self._retry(_do_list, "list_memories(reflection)")
        except Exception as exc:  # noqa: BLE001
            logger.error("AgentArts get_user_profile failed for user_id=%s: %s", user_id, exc)
            return {}

        items = getattr(resp, "items", None) or []
        if not items:
            return {}

        preferences: list[str] = []
        facts: list[str] = []
        for item in items:
            item_dict = item if isinstance(item, dict) else item.__dict__
            text = item_dict.get("content", "")
            if not text:
                continue
            lower = text.lower()
            if any(kw in lower for kw in ("prefer", "like", "love", "hate", "favorite")):
                preferences.append(text)
            else:
                facts.append(text)

        profile: dict[str, Any] = {}
        if preferences:
            profile["preferences"] = preferences
        if facts:
            profile["facts"] = facts
        return profile


__all__ = ["AgentArtsMemoryClient"]