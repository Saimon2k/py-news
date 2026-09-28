import hashlib
import re
import unicodedata
from datetime import datetime
from typing import Sequence

from src.core.models import CollectedMessage


class NewsCollectorService:
    @staticmethod
    def normalize_text(text: str | None) -> str:
        if not text:
            return ""

        text = unicodedata.normalize("NFKC", text).casefold()
        text = re.sub(r"(?:https?://|www\.)\S+", " ", text)
        text = "".join(
            char for char in text
            if not unicodedata.category(char).startswith("C")
        )
        text = "".join(
            char if char.isalnum() or char.isspace() else " "
            for char in text
        )
        return " ".join(text.split())

    @staticmethod
    def calculate_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def process_and_deduplicate(
        self, messages: Sequence[CollectedMessage]
    ) -> list[CollectedMessage]:
        canonical_by_hash: dict[str, int] = {}
        processed: list[CollectedMessage] = []

        for message in sorted(messages, key=lambda item: item.date):
            message.is_canonical = True
            message.duplicate_of_message_id = None

            normalized = self.normalize_text(message.text)
            message.normalized_text = normalized or None
            message.content_hash = self.calculate_hash(normalized) if normalized else None

            if message.content_hash is not None:
                canonical_id = canonical_by_hash.get(message.content_hash)
                if canonical_id is None:
                    canonical_by_hash[message.content_hash] = message.message_id
                else:
                    message.is_canonical = False
                    message.duplicate_of_message_id = canonical_id

            processed.append(message)

        return processed
