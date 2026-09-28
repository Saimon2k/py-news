from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.models import MessageType, QueueStatus


class Base(DeclarativeBase):
    pass


class DBUser(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class DBUserChannel(Base):
    __tablename__ = "user_channels"
    __table_args__ = (UniqueConstraint("user_id", "channel_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel_id: Mapped[int] = mapped_column(Integer)
    channel_username: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class DBChannelState(Base):
    __tablename__ = "channel_states"
    __table_args__ = (UniqueConstraint("user_id", "channel_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel_id: Mapped[int] = mapped_column(Integer)
    last_digest_date: Mapped[datetime] = mapped_column(DateTime)
    last_message_id: Mapped[int] = mapped_column(Integer)


class DBDigestQueue(Base):
    __tablename__ = "digest_queues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus, values_callable=lambda enum: [item.value for item in enum]),
        default=QueueStatus.ACTIVE,
    )
    source_batch_path: Mapped[str] = mapped_column(String, default="")
    items: Mapped[list["DBDigestItem"]] = relationship(
        back_populates="queue", cascade="all, delete-orphan", lazy="selectin"
    )


class DBDigestItem(Base):
    __tablename__ = "digest_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest_queue_id: Mapped[int] = mapped_column(ForeignKey("digest_queues.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer)
    channel_id: Mapped[int] = mapped_column(Integer)
    channel_username: Mapped[str | None] = mapped_column(String, nullable=True)
    message_id: Mapped[int] = mapped_column(Integer)
    message_url: Mapped[str] = mapped_column(String)
    type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, values_callable=lambda enum: [item.value for item in enum])
    )
    preview_text: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    queue: Mapped[DBDigestQueue] = relationship(back_populates="items")
