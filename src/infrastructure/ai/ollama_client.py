import json
from typing import Any

import structlog
from ollama import AsyncClient
from pydantic import BaseModel, ConfigDict, Field, ValidationError


logger = structlog.get_logger(__name__)


class SelectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    reason: str
    summary: str = ""
    source_ids: list[int] = Field(default_factory=list)


class NewsSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected: list[SelectionItem] = Field(default_factory=list)
    ads: list[int] = Field(default_factory=list)
    duplicates: list[int] = Field(default_factory=list)


class OllamaNewsClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.client = AsyncClient(host=base_url)
        self.model = model

    async def filter_news(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        if not messages:
            return {"selected": [], "ads": [], "duplicates": []}

        prompt = (
            "Сгруппируй реальные новости об одном событии, даже если формулировки разные; "
            "исключи рекламу и скам. Для каждой группы верни один id (каноничная новость), "
            "краткое суммари только по фактам публикаций и source_ids всех публикаций группы. "
            "Каждая новость должна попасть не более чем в одну группу. Верни JSON по схеме; "
            "ID должны быть только из входных данных.\n"
            + json.dumps(messages, ensure_ascii=False)
        )
        for attempt in range(2):
            try:
                response = await self.client.chat(
                    model=self.model,
                    format=NewsSelection.model_json_schema(),
                    messages=[
                        {"role": "system", "content": "Ты редактор новостного дайджеста. Не выдумывай факты."},
                        {"role": "user", "content": prompt},
                    ],
                )
                result = NewsSelection.model_validate_json(response.message.content)
                valid_ids = {message["id"] for message in messages}
                selected = []
                used_sources: set[int] = set()
                for item in result.selected:
                    if item.id not in valid_ids:
                        continue
                    source_ids = [source_id for source_id in item.source_ids
                                  if source_id in valid_ids and source_id not in used_sources]
                    if not source_ids:
                        source_ids = [item.id]
                    used_sources.update(source_ids)
                    selected.append({**item.model_dump(), "source_ids": source_ids})
                return {"selected": selected, "ads": result.ads, "duplicates": result.duplicates}
            except (ValidationError, ValueError, TypeError) as error:
                logger.warning(
                    "Invalid response from Ollama",
                    attempt=attempt + 1,
                    error=str(error),
                    response_length=(len(response.message.content) if "response" in locals() else 0),
                )
                if attempt == 1:
                    return {"selected": [], "ads": [], "duplicates": []}
        raise RuntimeError("Unreachable Ollama retry state")
