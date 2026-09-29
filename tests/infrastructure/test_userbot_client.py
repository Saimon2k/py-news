from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.infrastructure.telegram.userbot_client import TelethonUserbotClient


class TelegramClientStub:
    def __init__(self, messages) -> None:
        self.messages = messages
        self.iter_messages_args = None

    async def get_entity(self, channel):
        return SimpleNamespace(id=123)

    async def iter_messages(self, *args, **kwargs):
        self.iter_messages_args = (args, kwargs)
        for message in self.messages:
            yield message


@pytest.mark.asyncio
async def test_get_history_reads_latest_messages_and_filters_by_date() -> None:
    offset_date = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    client = TelegramClientStub([
        SimpleNamespace(
            id=1,
            date=offset_date - timedelta(seconds=1),
            message="Старая публикация",
            media=None,
        ),
        SimpleNamespace(
            id=2,
            date=offset_date,
            message="Новая публикация",
            media=None,
        ),
    ])

    result = await TelethonUserbotClient(client).get_history(
        "news_feed", offset_date=offset_date, limit=100
    )

    assert client.iter_messages_args == ((await client.get_entity("news_feed"),), {"limit": 100})
    assert [message.message_id for message in result] == [2]
