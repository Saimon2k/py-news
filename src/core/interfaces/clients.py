from datetime import datetime
from typing import Any, Protocol

from src.core.models import CollectedMessage


class UserbotClient(Protocol):
    async def start(self) -> None: ...
    async def get_history(
        self,
        channel: int | str,
        offset_date: datetime | None = None,
        limit: int = 100,
    ) -> list[CollectedMessage]: ...
    async def resolve_channel_peer(self, target: str) -> dict[str, Any]: ...
    async def close(self) -> None: ...


class OllamaClient(Protocol):
    async def filter_news(self, messages: list[dict[str, Any]]) -> dict[str, Any]: ...
