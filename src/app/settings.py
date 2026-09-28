import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class Settings:
    database_url: str
    ollama_url: str
    ollama_model: str
    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str
    telegram_bot_token: str
    telegram_session_path: str
    telegram_proxy: tuple[str, int, str] | None
    log_level: str = "INFO"


def load_settings(root: Path | None = None) -> Settings:
    root = root or Path.cwd()
    data: dict[str, Any] = {}
    for filename in ("config.toml", ".secrets.toml"):
        path = root / filename
        if path.exists():
            with path.open("rb") as stream:
                parsed = tomllib.load(stream)
                data.update(parsed.get("default", parsed))

    telegram = data.get("Telegram", {})
    ollama = data.get("Ollama", {})
    storage = data.get("Storage", {})
    env = os.environ
    values = {
        "database_url": env.get("PYNEWS_DATABASE_URL", storage.get("DatabasePath", data.get("DATABASE_URL", "sqlite+aiosqlite:///./news_digest.db"))),
        "ollama_url": env.get("PYNEWS_OLLAMA_URL", ollama.get("Url", "http://localhost:11434")),
        "ollama_model": env.get("PYNEWS_OLLAMA_MODEL", ollama.get("Model", "llama3")),
        "telegram_api_id": env.get("PYNEWS_TELEGRAM_API_ID", telegram.get("ApiId", 0)),
        "telegram_api_hash": env.get("PYNEWS_TELEGRAM_API_HASH", telegram.get("ApiHash", "")),
        "telegram_phone": env.get("PYNEWS_TELEGRAM_PHONE", telegram.get("PhoneNumber", "")),
        "telegram_bot_token": env.get("PYNEWS_TELEGRAM_BOT_TOKEN", telegram.get("BotToken", "")),
        "telegram_session_path": env.get("PYNEWS_TELEGRAM_SESSION", telegram.get("SessionPath", "./storage/telegram")),
        "telegram_proxy": _parse_mtproxy(env.get("PYNEWS_TELEGRAM_PROXY", telegram.get("Proxy", ""))),
        "log_level": env.get("PYNEWS_LOG_LEVEL", data.get("Logging", {}).get("Level", "INFO")),
    }
    missing = [key for key in ("telegram_api_id", "telegram_api_hash", "telegram_phone", "telegram_bot_token") if not values[key]]
    if missing:
        raise ValueError(
            "Не заданы настройки Telegram: " + ", ".join(missing)
            + ". Заполните .secrets.toml или переменные PYNEWS_TELEGRAM_*."
        )
    if isinstance(values["telegram_api_id"], bool):
        raise ValueError("PYNEWS_TELEGRAM_API_ID должен быть числом")
    values["telegram_api_id"] = int(values["telegram_api_id"])
    return Settings(**values)


def _parse_mtproxy(value: str) -> tuple[str, int, str] | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "tg" or parsed.netloc != "proxy":
        raise ValueError("Telegram Proxy должен быть ссылкой формата tg://proxy?server=...&port=...&secret=...")
    query = parse_qs(parsed.query)
    try:
        host = query["server"][0]
        port = int(query["port"][0])
        secret = query["secret"][0]
    except (KeyError, IndexError, ValueError) as error:
        raise ValueError("В ссылке Telegram MTProxy отсутствуют server, port или secret") from error
    if not host or not 1 <= port <= 65535 or len(secret) not in (32, 34):
        raise ValueError("Некорректные параметры Telegram MTProxy")
    return host, port, secret
