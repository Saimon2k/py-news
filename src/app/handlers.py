from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

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
    sessions: async_sessionmaker,
    digest_service: DigestService,
    userbot: TelethonUserbotClient,
) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "Привет! Команды: /add <канал>, /list, /remove <канал>, /news, /next"
        )

    @router.message(Command("add"))
    async def add_channel(message: Message) -> None:
        args = (message.text or "").split(maxsplit=1)
        if len(args) != 2:
            await message.answer("Формат: /add <@username или ссылка>")
            return
        try:
            info = await userbot.resolve_channel_peer(args[1])
            async with sessions.begin() as session:
                users = SqlUserRepository(session)
                user = await users.get_or_create(message.from_user.id)
                channels = SqlUserChannelRepository(session)
                if await channels.get(user.id, info["id"]):
                    await message.answer("Канал уже добавлен.")
                    return
                await channels.add(UserChannel(
                    user_id=user.id,
                    channel_id=info["id"],
                    channel_username=info["username"],
                    title=info["title"],
                ))
            await message.answer(f"Добавлен канал: {info['title']}")
        except Exception as error:
            await message.answer(f"Не удалось добавить канал: {error}")

    @router.message(Command("list"))
    async def list_channels(message: Message) -> None:
        async with sessions.begin() as session:
            user = await SqlUserRepository(session).get_by_telegram_id(message.from_user.id)
            channels = await SqlUserChannelRepository(session).list_for_user(user.id) if user else []
        await message.answer("\n".join(f"{c.title} (@{c.channel_username or c.channel_id})" for c in channels) or "Список каналов пуст.")

    @router.message(Command("remove"))
    async def remove_channel(message: Message) -> None:
        args = (message.text or "").split(maxsplit=1)
        if len(args) != 2:
            await message.answer("Формат: /remove <@username или ID>")
            return
        async with sessions.begin() as session:
            user = await SqlUserRepository(session).get_by_telegram_id(message.from_user.id)
            removed = await SqlUserChannelRepository(session).remove(user.id, args[1]) if user else False
        await message.answer("Канал удалён." if removed else "Канал не найден.")

    @router.message(Command("news"))
    async def collect_news(message: Message) -> None:
        try:
            async with sessions.begin() as session:
                users = SqlUserRepository(session)
                user = await users.get_or_create(message.from_user.id)
                channels = await SqlUserChannelRepository(session).list_for_user(user.id)
                if not channels:
                    await message.answer("Сначала добавьте каналы командой /add.")
                    return
                queue = await digest_service.build_queue(
                    user.id,
                    channels,
                    SqlChannelStateRepository(session),
                    SqlDigestQueueRepository(session),
                )
            await message.answer(f"Дайджест готов: {len(queue.items)} новостей. Используйте /next.")
        except Exception as error:
            await message.answer(f"Не удалось собрать дайджест: {error}")

    @router.message(Command("next"))
    async def next_news(message: Message) -> None:
        async with sessions.begin() as session:
            user = await SqlUserRepository(session).get_by_telegram_id(message.from_user.id)
            item = await SqlDigestQueueRepository(session).next_unsent(user.id) if user else None
        if item:
            preview = (item.preview_text or "").strip()
            text = f"{preview[:3000]}\n\n{item.message_url}"
            await message.answer(text)
            async with sessions.begin() as session:
                await SqlDigestQueueRepository(session).mark_sent(item.id)
        else:
            await message.answer("Непрочитанных новостей нет. Используйте /news для нового сбора.")

    return router
