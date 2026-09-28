from datetime import datetime

from src.core.models import CollectedMessage, DigestQueue, MessageType, User


def test_domain_models_validate_message_and_queue_defaults() -> None:
    message = CollectedMessage(
        user_id=1,
        channel_id=10,
        message_id=15,
        date=datetime(2026, 1, 1),
        text="News",
        type=MessageType.TEXT,
    )
    queue = DigestQueue(user_id=1)

    assert message.type is MessageType.TEXT
    assert queue.items == []
    assert User(telegram_user_id=1).id is None
