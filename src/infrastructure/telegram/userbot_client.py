from datetime import datetime, timezone
from typing import Any

from telethon import TelegramClient

from src.core.models import CollectedMessage, MessageType


class TelethonUserbotClient:
    def __init__(self, client: TelegramClient) -> None:
        self.client = client

    async def start(self) -> None:
        if not self.client.is_connected():
            await self.client.start()

    async def close(self) -> None:
        if self.client.is_connected():
            await self.client.disconnect()

    async def get_history(
        self,
        channel: int | str,
        offset_date: datetime | None = None,
        limit: int = 100,
    ) -> list[CollectedMessage]:
        entity = await self.client.get_entity(channel)
        channel_id = int(getattr(entity, "id"))
        result = []
        async for message in self.client.iter_messages(
            entity, limit=limit
        ):
            if offset_date and message.date < _as_utc(offset_date):
                continue
            text = message.message or None
            media = bool(message.media)
            kind = MessageType.MEDIA_WITH_CAPTION if media and text else (
                MessageType.MEDIA_WITHOUT_TEXT if media else MessageType.TEXT
            )
            result.append(CollectedMessage(
                user_id=0,
                channel_id=channel_id,
                message_id=message.id,
                date=message.date,
                text=text,
                type=kind,
            ))
        return result

    async def resolve_channel_peer(self, target: str) -> dict[str, Any]:
        entity = await self.client.get_entity(target)
        return {
            "id": int(entity.id),
            "username": getattr(entity, "username", None),
            "title": getattr(entity, "title", None) or getattr(entity, "first_name", target),
        }


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
