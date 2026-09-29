import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import DigestItem, DigestQueue, MessageType, UserChannel
from src.infrastructure.database.models import Base, DBDigestItem, DBDigestQueue
from src.infrastructure.database.repositories import (
    SqlDigestQueueRepository,
    SqlUserChannelRepository,
    SqlUserRepository,
)
from src.infrastructure.database.session import Database


@pytest.mark.asyncio
async def test_user_channel_and_digest_repositories() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions.begin() as session:
        user = await SqlUserRepository(session).get_or_create(1001)
        channels = SqlUserChannelRepository(session)
        saved = await channels.add(UserChannel(
            user_id=user.id,
            channel_id=42,
            channel_username="sample",
            title="Sample",
        ))
        assert saved.id is not None

    async with sessions.begin() as session:
        user = await SqlUserRepository(session).get_by_telegram_id(1001)
        assert user is not None
        repo = SqlUserChannelRepository(session)
        assert len(await repo.list_for_user(user.id)) == 1
        assert await repo.remove(user.id, "@sample") is True
        assert await repo.list_for_user(user.id) == []

    await engine.dispose()


@pytest.mark.asyncio
async def test_database_initialize_clears_queues_but_preserves_channels() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions.begin() as session:
        user = await SqlUserRepository(session).get_or_create(1002)
        await SqlUserChannelRepository(session).add(UserChannel(
            user_id=user.id,
            channel_id=42,
            title="Sample",
        ))
        await SqlDigestQueueRepository(session).create(DigestQueue(
            user_id=user.id,
            items=[DigestItem(
                order_index=0,
                channel_id=42,
                message_id=1,
                message_url="https://t.me/sample/1",
                type=MessageType.TEXT,
            )],
        ))

    database = Database("sqlite+aiosqlite:///:memory:")
    database.engine = engine
    database.sessions = sessions
    await database.initialize()

    async with sessions() as session:
        assert await session.scalar(select(DBDigestQueue.id)) is None
        assert await session.scalar(select(DBDigestItem.id)) is None
        assert len(await SqlUserChannelRepository(session).list_for_user(1)) == 1

    await engine.dispose()
