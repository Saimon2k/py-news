from datetime import datetime, timedelta, timezone

import pytest

from src.core.models import ChannelState, CollectedMessage, MessageType, UserChannel
from src.core.services.digest import DigestService


class UserbotStub:
    def __init__(self):
        self.requested = []

    async def get_history(self, channel, offset_date=None, limit=100):
        self.requested.append((channel, offset_date, limit))
        return [
            CollectedMessage(user_id=0, channel_id=123, message_id=2, date=offset_date + timedelta(minutes=1), text="Повтор", type=MessageType.TEXT),
            CollectedMessage(user_id=0, channel_id=123, message_id=1, date=offset_date, text="Повтор!", type=MessageType.TEXT),
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


@pytest.mark.asyncio
async def test_build_queue_discards_messages_older_than_offset_date() -> None:
    class UserbotWithOldMessage(UserbotStub):
        async def get_history(self, channel, offset_date=None, limit=100):
            self.requested.append((channel, offset_date, limit))
            return [
                CollectedMessage(
                    user_id=0,
                    channel_id=123,
                    message_id=1,
                    date=offset_date - timedelta(seconds=1),
                    text="Старая новость",
                    type=MessageType.TEXT,
                ),
                CollectedMessage(
                    user_id=0,
                    channel_id=123,
                    message_id=2,
                    date=offset_date,
                    text="Новая новость",
                    type=MessageType.TEXT,
                ),
            ]

    class CapturingOllamaStub(OllamaStub):
        def __init__(self):
            self.messages = []

        async def filter_news(self, messages):
            self.messages = messages
            return {"selected": [{"id": 0, "reason": "новость"}]}

    userbot = UserbotWithOldMessage()
    ollama = CapturingOllamaStub()
    service = DigestService(userbot, ollama)
    channel = UserChannel(user_id=9, channel_id=123, title="News")

    queue = await service.build_queue(9, [channel], StateRepositoryStub(), QueueRepositoryStub())

    assert [message["text"] for message in ollama.messages] == ["Новая новость"]
    assert [item.message_id for item in queue.items] == [2]


@pytest.mark.asyncio
async def test_build_queue_treats_naive_saved_state_as_utc() -> None:
    saved_date = datetime(2026, 1, 1, 12)

    class StateRepositoryWithSavedDate(StateRepositoryStub):
        async def get(self, user_id, channel_id):
            return ChannelState(
                user_id=user_id,
                channel_id=channel_id,
                last_digest_date=saved_date,
                last_message_id=1,
            )

    userbot = UserbotStub()
    service = DigestService(userbot, OllamaStub())
    channel = UserChannel(user_id=9, channel_id=123, title="News")

    await service.build_queue(9, [channel], StateRepositoryWithSavedDate(), QueueRepositoryStub())

    assert userbot.requested[0][1] == saved_date.replace(tzinfo=timezone.utc)
