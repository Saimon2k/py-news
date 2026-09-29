from datetime import datetime, time, timedelta, timezone

from src.core.interfaces.clients import OllamaClient, UserbotClient
from src.core.models import ChannelState, DigestItem, DigestQueue
from src.core.services.collector import NewsCollectorService

MOSCOW_TZ = timezone(timedelta(hours=3))


class DigestService:
    def __init__(
        self, userbot: UserbotClient, ollama: OllamaClient, initial_history_limit: int = 100
    ) -> None:
        self.userbot = userbot
        self.ollama = ollama
        self.collector = NewsCollectorService()
        self.initial_history_limit = initial_history_limit

    async def build_queue(self, user_id: int, channels, states, queues) -> DigestQueue:
        messages = []
        updates: list[ChannelState] = []
        for channel in channels:
            state = await states.get(user_id, channel.channel_id)
            target = channel.channel_username or channel.channel_id
            offset_date = state.last_digest_date if state else _yesterday_18_moscow()
            try:
                history = await self.userbot.get_history(
                    target,
                    offset_date,
                    limit=self.initial_history_limit,
                )
            except Exception as error:
                raise RuntimeError(
                    f"Не удалось прочитать канал «{channel.title}» "
                    f"({channel.channel_username or channel.channel_id}): {error}"
                ) from error
            for message in history:
                message.user_id = user_id
            messages.extend(history)
            if history:
                latest = max(history, key=lambda item: (item.date, item.message_id))
                updates.append(ChannelState(
                    user_id=user_id,
                    channel_id=channel.channel_id,
                    last_digest_date=latest.date,
                    last_message_id=latest.message_id,
                ))

        unique = [m for m in self.collector.process_and_deduplicate(messages) if m.is_canonical]
        payload = [
            {
                "id": index,
                "channel": message.channel_id,
                "date": message.date.isoformat(),
                "text": message.text or "",
                "type": message.type.value,
            }
            for index, message in enumerate(unique)
        ]
        filtered = await self.ollama.filter_news(payload) if payload else {"selected": []}
        selected = {item["id"]: item for item in filtered.get("selected", [])}
        digest_items = []
        for index, message in enumerate(unique):
            decision = selected.get(index)
            if decision is None:
                continue
            channel = next(c for c in channels if c.channel_id == message.channel_id)
            username = channel.channel_username
            message_url = (
                f"https://t.me/{username}/{message.message_id}"
                if username
                else f"https://t.me/c/{message.channel_id}/{message.message_id}"
            )
            digest_items.append(DigestItem(
                order_index=len(digest_items),
                channel_id=message.channel_id,
                channel_username=username,
                message_id=message.message_id,
                message_url=message_url,
                type=message.type,
                preview_text=message.text,
                reason=decision.get("reason"),
            ))

        queue = await queues.create(DigestQueue(user_id=user_id, items=digest_items))
        for state in updates:
            await states.save(state)
        return queue


def _yesterday_18_moscow() -> datetime:
    now_moscow = datetime.now(MOSCOW_TZ)
    yesterday = now_moscow.date() - timedelta(days=1)
    return datetime.combine(yesterday, time(18), tzinfo=MOSCOW_TZ).astimezone(timezone.utc)
