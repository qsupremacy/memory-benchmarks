"""Protocol shared by every memory backend in this project.

Lives in its own module (not in agentarts_memory.py) so that backend
implementations can be imported independently — e.g. ``aws_memory`` does
not need the HuaweiCloud agentarts SDK installed just to satisfy
duck-typing.
"""
from __future__ import annotations

from typing import Any, Protocol


class MemoryBackend(Protocol):
    """Duck-typed surface used by benchmarks.

    Satisfied by Mem0Client, AgentArtsMemoryClient, AwsAgentCoreMemoryClient.
    """

    async def add(
        self,
        messages: list[dict[str, Any]],
        user_id: str,
        timestamp: int | None = ...,
    ) -> dict[str, Any] | None: ...

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = ...,
        score_debug: bool = ...,
    ) -> list[dict[str, Any]]: ...

    async def get_user_profile(self, user_id: str) -> dict[str, Any]: ...

    async def close(self) -> None: ...

    async def __aenter__(self) -> "MemoryBackend": ...

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...


__all__ = ["MemoryBackend"]
