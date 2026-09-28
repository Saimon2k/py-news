from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.models import ChannelState, DigestItem, DigestQueue, User, UserChannel
from src.infrastructure.database.models import (
    DBChannelState,
    DBDigestItem,
    DBDigestQueue,
    DBUser,
    DBUserChannel,
)


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        row = await self.session.scalar(
            select(DBUser).where(DBUser.telegram_user_id == telegram_user_id)
        )
        return User.model_validate(row) if row else None

    async def get_or_create(self, telegram_user_id: int) -> User:
        user = await self.get_by_telegram_id(telegram_user_id)
        if user:
            return user
        row = DBUser(telegram_user_id=telegram_user_id)
        self.session.add(row)
        await self.session.flush()
        return User.model_validate(row)


class SqlUserChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: int) -> list[UserChannel]:
        rows = await self.session.scalars(
            select(DBUserChannel).where(DBUserChannel.user_id == user_id).order_by(DBUserChannel.title)
        )
        return [UserChannel.model_validate(row) for row in rows]

    async def get(self, user_id: int, channel_id: int) -> UserChannel | None:
        row = await self.session.scalar(
            select(DBUserChannel).where(
                DBUserChannel.user_id == user_id,
                DBUserChannel.channel_id == channel_id,
            )
        )
        return UserChannel.model_validate(row) if row else None

    async def add(self, channel: UserChannel) -> UserChannel:
        row = DBUserChannel(**channel.model_dump(exclude={"id", "created_at"}))
        self.session.add(row)
        await self.session.flush()
        return UserChannel.model_validate(row)

    async def remove(self, user_id: int, target: str) -> bool:
        statement = select(DBUserChannel).where(DBUserChannel.user_id == user_id)
        if target.lstrip("-").isdigit():
            statement = statement.where(DBUserChannel.channel_id == int(target))
        else:
            statement = statement.where(DBUserChannel.channel_username == target.lstrip("@"))
        row = await self.session.scalar(statement)
        if row is None:
            return False
        await self.session.delete(row)
        return True


class SqlChannelStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int, channel_id: int) -> ChannelState | None:
        row = await self.session.scalar(
            select(DBChannelState).where(
                DBChannelState.user_id == user_id,
                DBChannelState.channel_id == channel_id,
            )
        )
        return ChannelState.model_validate(row) if row else None

    async def save(self, state: ChannelState) -> None:
        row = await self.session.scalar(
            select(DBChannelState).where(
                DBChannelState.user_id == state.user_id,
                DBChannelState.channel_id == state.channel_id,
            )
        )
        if row is None:
            row = DBChannelState(user_id=state.user_id, channel_id=state.channel_id)
            self.session.add(row)
        row.last_digest_date = state.last_digest_date
        row.last_message_id = state.last_message_id


class SqlDigestQueueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, queue: DigestQueue) -> DigestQueue:
        row = DBDigestQueue(
            user_id=queue.user_id,
            status=queue.status,
            source_batch_path=queue.source_batch_path,
            items=[
                DBDigestItem(**item.model_dump(exclude={"id", "digest_queue_id"}))
                for item in queue.items
            ],
        )
        self.session.add(row)
        await self.session.flush()
        return DigestQueue.model_validate(row)

    async def get_active(self, user_id: int) -> DigestQueue | None:
        row = await self.session.scalar(
            select(DBDigestQueue)
            .options(selectinload(DBDigestQueue.items))
            .where(DBDigestQueue.user_id == user_id, DBDigestQueue.status == "active")
            .order_by(DBDigestQueue.created_at.desc())
        )
        return DigestQueue.model_validate(row) if row else None

    async def next_unsent(self, user_id: int) -> DigestItem | None:
        row = await self.session.scalar(
            select(DBDigestItem)
            .join(DBDigestQueue)
            .where(DBDigestQueue.user_id == user_id, DBDigestItem.is_sent.is_(False))
            .order_by(DBDigestQueue.created_at.desc(), DBDigestItem.order_index)
        )
        return DigestItem.model_validate(row) if row else None

    async def mark_sent(self, item_id: int) -> None:
        row = await self.session.get(DBDigestItem, item_id)
        if row is not None:
            row.is_sent = True
            remaining = await self.session.scalar(
                select(DBDigestItem.id).where(
                    DBDigestItem.digest_queue_id == row.digest_queue_id,
                    DBDigestItem.is_sent.is_(False),
                    DBDigestItem.id != row.id,
                ).limit(1)
            )
            if remaining is None:
                queue = await self.session.get(DBDigestQueue, row.digest_queue_id)
                if queue is not None:
                    queue.status = "completed"
