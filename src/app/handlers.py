from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon import TelegramClient, events

from src.core.models import UserChannel
from src.core.services.digest import DigestService
from src.infrastructure.database.repositories import (
    SqlChannelStateRepository,
    SqlDigestQueueRepository,
    SqlUserChannelRepository,
    SqlUserRepository,
)
from src.infrastructure.telegram.userbot_client import TelethonUserbotClient


def create_router(
    bot: TelegramClient,
    sessions: async_sessionmaker,
    digest_service: DigestService,
    userbot: TelethonUserbotClient,
) -> None:

    @bot.on(events.NewMessage(pattern=r"^/start(?:\s|$)"))
    async def start(message) -> None:
        await message.respond(
            "Привет! Команды: /add <канал>, /list, /remove <канал>, /news, /next"
        )

    @bot.on(events.NewMessage(pattern=r"^/add(?:\s|$)"))
    async def add_channel(message) -> None:
        args = (message.raw_text or "").split(maxsplit=1)
        if len(args) != 2:
            await message.respond("Формат: /add <@username или ссылка>")
            return
        try:
            info = await userbot.resolve_channel_peer(args[1])
            async with sessions.begin() as session:
                users = SqlUserRepository(session)
                user = await users.get_or_create(message.sender_id)
                channels = SqlUserChannelRepository(session)
                if await channels.get(user.id, info["id"]):
                    await message.respond("Канал уже добавлен.")
                    return
                await channels.add(UserChannel(
                    user_id=user.id,
                    channel_id=info["id"],
                    channel_username=info["username"],
                    title=info["title"],
                ))
            await message.respond(f"Добавлен канал: {info['title']}")
        except Exception as error:
            await message.respond(f"Не удалось добавить канал: {error}")

    @bot.on(events.NewMessage(pattern=r"^/list(?:\s|$)"))
    async def list_channels(message) -> None:
        async with sessions.begin() as session:
            user = await SqlUserRepository(session).get_by_telegram_id(message.sender_id)
            channels = await SqlUserChannelRepository(session).list_for_user(user.id) if user else []
        await message.respond("\n".join(f"{c.title} (@{c.channel_username or c.channel_id})" for c in channels) or "Список каналов пуст.")

    @bot.on(events.NewMessage(pattern=r"^/remove(?:\s|$)"))
    async def remove_channel(message) -> None:
        args = (message.raw_text or "").split(maxsplit=1)
        if len(args) != 2:
            await message.respond("Формат: /remove <@username или ID>")
            return
        async with sessions.begin() as session:
            user = await SqlUserRepository(session).get_by_telegram_id(message.sender_id)
            removed = await SqlUserChannelRepository(session).remove(user.id, args[1]) if user else False
        await message.respond("Канал удалён." if removed else "Канал не найден.")

    @bot.on(events.NewMessage(pattern=r"^/news(?:\s|$)"))
    async def collect_news(message) -> None:
        try:
            await message.respond("Начинаю сбор новостей по каналам. Это может занять несколько минут…")
            async with sessions() as session:
                users = SqlUserRepository(session)
                user = await users.get_or_create(message.sender_id)
                channels = await SqlUserChannelRepository(session).list_for_user(user.id)
                if not channels:
                    await message.respond("Сначала добавьте каналы командой /add.")
                    return
                queue = await digest_service.build_queue(
                    user.id,
                    channels,
                    SqlChannelStateRepository(session),
                    SqlDigestQueueRepository(session),
                )
                await session.commit()
            await message.respond(f"Дайджест готов: {len(queue.items)} новостей. Используйте /next.")
        except Exception as error:
            await message.respond(f"Не удалось собрать дайджест: {error}")

    @bot.on(events.NewMessage(pattern=r"^/next(?:\s|$)"))
    async def next_news(message) -> None:
        async with sessions.begin() as session:
            user = await SqlUserRepository(session).get_by_telegram_id(message.sender_id)
            item = await SqlDigestQueueRepository(session).next_unsent(user.id) if user else None
        if item:
            preview = (item.preview_text or "").strip()
            sources = item.source_urls or [item.message_url]
            text = f"{preview[:3000]}\n\nИсточники:\n" + "\n".join(sources)
            await message.respond(text)
            async with sessions.begin() as session:
                await SqlDigestQueueRepository(session).mark_sent(item.id)
        else:
            await message.respond("Непрочитанных новостей нет. Используйте /news для нового сбора.")
