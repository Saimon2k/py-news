from datetime import datetime, timedelta, timezone

import pytest

from src.core.models import CollectedMessage, MessageType, UserChannel
from src.core.services.digest import DigestService


class UserbotStub:
    def __init__(self):
        self.requested = []

    async def get_history(self, channel, offset_date=None, limit=100):
        self.requested.append((channel, offset_date, limit))
        start = datetime(2026, 1, 1)
        return [
            CollectedMessage(user_id=0, channel_id=123, message_id=2, date=start + timedelta(minutes=1), text="Повтор", type=MessageType.TEXT),
            CollectedMessage(user_id=0, channel_id=123, message_id=1, date=start, text="Повтор!", type=MessageType.TEXT),
        ]


class OllamaStub:
    async def filter_news(self, messages):
        return {"selected": [{"id": 0, "reason": "новость"}]}


class StateRepositoryStub:
    def __init__(self):
        self.saved = []

    async def get(self, user_id, channel_id):
        return None

    async def save(self, state):
        self.saved.append(state)


class QueueRepositoryStub:
    async def create(self, queue):
        return queue


@pytest.mark.asyncio
async def test_build_queue_deduplicates_before_llm_and_tracks_latest_message() -> None:
    userbot = UserbotStub()
    service = DigestService(userbot, OllamaStub(), initial_history_limit=40)
    states = StateRepositoryStub()
    channel = UserChannel(
        user_id=9,
        channel_id=123,
        channel_username="news_feed",
        title="News",
    )

    queue = await service.build_queue(9, [channel], states, QueueRepositoryStub())

    assert len(queue.items) == 1
    assert queue.items[0].message_id == 1
    assert queue.items[0].message_url == "https://t.me/news_feed/1"
    assert states.saved[0].last_message_id == 2
    target, offset_date, limit = userbot.requested[0]
    assert target == "news_feed"
    assert offset_date.tzinfo == timezone.utc
    assert offset_date.hour == 15  # 18:00 Moscow is 15:00 UTC.
    assert limit == 40
