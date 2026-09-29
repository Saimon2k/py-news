from datetime import datetime, time, timedelta, timezone

from src.core.interfaces.clients import OllamaClient, UserbotClient
from src.core.models import ChannelState, DigestItem, DigestQueue
from src.core.services.collector import NewsCollectorService

MOSCOW_TZ = timezone(timedelta(hours=3))
MVP_FALLBACK_LIMIT = 10


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
            offset_date = _as_utc(state.last_digest_date) if state else _yesterday_18_moscow()
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
            history = [message for message in history if message.date >= offset_date]
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

        processed = self.collector.process_and_deduplicate(messages)
        payload = [
            {
                "id": index,
                "channel": message.channel_id,
                "date": message.date.isoformat(),
                "text": message.text or "",
                "type": message.type.value,
            }
            for index, message in enumerate(processed)
        ]
        filtered = await self.ollama.filter_news(payload) if payload else {"selected": []}
        selected = {item["id"]: item for item in filtered.get("selected", [])}
        if processed and not selected:
            selected = {
                index: {"id": index, "reason": "MVP fallback", "summary": "", "source_ids": [index]}
                for index in range(max(0, len(processed) - MVP_FALLBACK_LIMIT), len(processed))
            }
        digest_items = []
        for index, message in enumerate(processed):
            decision = selected.get(index)
            if decision is None:
                continue
            channel = next(c for c in channels if c.channel_id == message.channel_id)
            source_ids = decision.get("source_ids") or [index]
            source_ids = [
                source_id for source_id in source_ids
                if isinstance(source_id, int) and 0 <= source_id < len(processed)
            ]
            if index not in source_ids:
                source_ids.insert(0, index)
            source_urls = []
            for source_id in source_ids:
                source = processed[source_id]
                source_channel = next(c for c in channels if c.channel_id == source.channel_id)
                source_username = source_channel.channel_username
                source_urls.append(
                    f"https://t.me/{source_username}/{source.message_id}"
                    if source_username
                    else f"https://t.me/c/{source.channel_id}/{source.message_id}"
                )
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
                preview_text=decision.get("summary") or message.text,
                reason=decision.get("reason"),
                source_urls=source_urls,
            ))

        queue = await queues.create(DigestQueue(user_id=user_id, items=digest_items))
        for state in updates:
            await states.save(state)
        return queue


def _yesterday_18_moscow() -> datetime:
    now_moscow = datetime.now(MOSCOW_TZ)
    yesterday = now_moscow.date() - timedelta(days=1)
    return datetime.combine(yesterday, time(18), tzinfo=MOSCOW_TZ).astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
