from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MessageType(StrEnum):
    TEXT = "text"
    MEDIA_WITH_CAPTION = "media_with_caption"
    MEDIA_WITHOUT_TEXT = "media_without_text"


class QueueStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class DomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, validate_assignment=True)


class User(DomainModel):
    id: int | None = None
    telegram_user_id: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserChannel(DomainModel):
    id: int | None = None
    user_id: int
    channel_id: int
    channel_username: str | None = None
    title: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChannelState(DomainModel):
    id: int | None = None
    user_id: int
    channel_id: int
    last_digest_date: datetime
    last_message_id: int


class CollectedMessage(DomainModel):
    id: int | None = None
    user_id: int
    channel_id: int
    message_id: int
    date: datetime
    text: str | None = None
    type: MessageType = MessageType.TEXT
    normalized_text: str | None = None
    content_hash: str | None = None
    is_canonical: bool = True
    duplicate_of_message_id: int | None = None


class DigestItem(DomainModel):
    id: int | None = None
    digest_queue_id: int | None = None
    order_index: int
    channel_id: int
    channel_username: str | None = None
    message_id: int
    message_url: str
    type: MessageType
    preview_text: str | None = None
    reason: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    is_sent: bool = False


class DigestQueue(DomainModel):
    id: int | None = None
    user_id: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: QueueStatus = QueueStatus.ACTIVE
    source_batch_path: str = ""
    items: list[DigestItem] = Field(default_factory=list)
