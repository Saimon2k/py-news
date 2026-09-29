from types import SimpleNamespace

import pytest

from src.infrastructure.ai.ollama_client import OllamaNewsClient, NewsSelection


class AsyncClientStub:
    def __init__(self, responses) -> None:
        self.responses = iter(responses)
        self.calls = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=next(self.responses)))


@pytest.mark.asyncio
async def test_filter_news_uses_schema_and_discards_unknown_ids() -> None:
    client = OllamaNewsClient("http://ollama", "test-model")
    stub = AsyncClientStub([
        '{"selected":[{"id":1,"reason":"новость"},{"id":99,"reason":"чужой"}],"ads":[],"duplicates":[]}'
    ])
    client.client = stub

    result = await client.filter_news([{"id": 1, "text": "Новость"}])

    assert result == {"selected": [{"id": 1, "reason": "новость"}], "ads": [], "duplicates": []}
    assert stub.calls[0]["format"] == NewsSelection.model_json_schema()


@pytest.mark.asyncio
async def test_filter_news_returns_empty_selection_after_invalid_responses() -> None:
    client = OllamaNewsClient("http://ollama", "test-model")
    client.client = AsyncClientStub(["not json", "not json"])

    result = await client.filter_news([{"id": 1, "text": "Новость"}])

    assert result == {"selected": [], "ads": [], "duplicates": []}
