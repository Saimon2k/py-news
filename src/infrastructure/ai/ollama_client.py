import json
from typing import Any

import structlog
from ollama import AsyncClient


logger = structlog.get_logger(__name__)


class OllamaNewsClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.client = AsyncClient(host=base_url)
        self.model = model

    async def filter_news(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        if not messages:
            return {"selected": [], "ads": [], "duplicates": []}

        prompt = (
            "Отбери реальные новости, исключи рекламу, скам и повторы. "
            "Верни JSON вида {\"selected\":[{\"id\":0,\"reason\":\"кратко\"}],"
            "\"ads\":[],\"duplicates\":[]}. ID должны быть только из входных данных.\n"
            + json.dumps(messages, ensure_ascii=False)
        )
        for attempt in range(2):
            try:
                response = await self.client.chat(
                    model=self.model,
                    format="json",
                    messages=[
                        {"role": "system", "content": "Ты редактор новостного дайджеста. Не выдумывай факты."},
                        {"role": "user", "content": prompt},
                    ],
                )
                result = json.loads(response.message.content)
                if not isinstance(result, dict) or not isinstance(result.get("selected"), list):
                    raise ValueError("Ollama returned an invalid selection schema")
                valid_ids = {message["id"] for message in messages}
                result["selected"] = [
                    item for item in result["selected"]
                    if isinstance(item, dict) and item.get("id") in valid_ids
                ]
                return result
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                logger.warning("Invalid response from Ollama", attempt=attempt + 1)
                if attempt == 1:
                    return {
                        "selected": [{"id": item["id"], "reason": "LLM fallback"} for item in messages],
                        "ads": [],
                        "duplicates": [],
                    }
        raise RuntimeError("Unreachable Ollama retry state")
