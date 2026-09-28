from datetime import datetime, timedelta

from src.core.services.collector import CollectedMessage, NewsCollectorService


def message(message_id: int, date: datetime, text: str | None) -> CollectedMessage:
    return CollectedMessage(
        user_id=1,
        channel_id=10,
        message_id=message_id,
        date=date,
        text=text,
    )


def test_normalize_text_removes_url_punctuation_and_emoji() -> None:
    collector = NewsCollectorService()

    normalized = collector.normalize_text(
        "  ПРИВЕТ!! Новости — уже тут: https://example.com/news 😊  "
    )

    assert normalized == "привет новости уже тут"


def test_normalize_text_handles_empty_text_and_unicode_compatibility() -> None:
    collector = NewsCollectorService()

    assert collector.normalize_text(None) == ""
    assert collector.normalize_text("ＡＢＣ   тест") == "abc тест"


def test_calculate_hash_is_stable_for_normalized_text() -> None:
    collector = NewsCollectorService()
    normalized = collector.normalize_text("Новость! https://example.com")

    assert collector.calculate_hash(normalized) == collector.calculate_hash("новость")


def test_deduplication_uses_earliest_message_and_preserves_input_order() -> None:
    collector = NewsCollectorService()
    start = datetime(2026, 1, 1, 10)
    messages = [
        message(102, start + timedelta(minutes=5), "  Событие А! "),
        message(101, start, "Событие А"),
        message(103, start + timedelta(minutes=10), ""),
    ]

    processed = collector.process_and_deduplicate(messages)

    assert [item.message_id for item in processed] == [101, 102, 103]
    assert processed[0].is_canonical is True
    assert processed[1].is_canonical is False
    assert processed[1].duplicate_of_message_id == 101
    assert processed[2].is_canonical is True
    assert processed[2].content_hash is None


def test_processing_again_resets_previous_deduplication_state() -> None:
    collector = NewsCollectorService()
    timestamp = datetime(2026, 1, 1, 10)
    first = message(1, timestamp, "Одинаково")
    second = message(2, timestamp + timedelta(minutes=1), "Одинаково")

    collector.process_and_deduplicate([first, second])
    second.text = "Теперь другое"
    processed = collector.process_and_deduplicate([first, second])

    assert all(item.is_canonical for item in processed)
    assert second.duplicate_of_message_id is None
