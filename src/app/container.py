from pathlib import Path

from telethon import TelegramClient, connection

from src.app.settings import Settings
from src.core.services.digest import DigestService
from src.infrastructure.ai.ollama_client import OllamaNewsClient
from src.infrastructure.database.session import Database
from src.infrastructure.telegram.auth_service import UserbotAuthService
from src.infrastructure.telegram.userbot_client import TelethonUserbotClient


class AppContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Telethon хранит файлы сессий рядом с указанным путём.
        Path(settings.telegram_session_path).parent.mkdir(parents=True, exist_ok=True)
        self.database = Database(settings.database_url)
        telethon_options = {}
        if settings.telegram_proxy:
            # Один и тот же прокси применяется к пользовательскому и бот-клиенту.
            telethon_options = {
                "connection": connection.ConnectionTcpMTProxyRandomizedIntermediate,
                "proxy": settings.telegram_proxy,
            }
        self.telethon = TelegramClient(
            settings.telegram_session_path,
            settings.telegram_api_id,
            settings.telegram_api_hash,
            **telethon_options,
        )
        self.bot_telethon = TelegramClient(
            # Отдельный файл не даёт пользовательской и бот-сессиям конфликтовать.
            f"{settings.telegram_session_path}_bot",
            settings.telegram_api_id,
            settings.telegram_api_hash,
            **telethon_options,
        )
        self.userbot = TelethonUserbotClient(self.telethon)
        self.auth = UserbotAuthService(self.telethon, settings.telegram_phone)
        self.ollama = OllamaNewsClient(settings.ollama_url, settings.ollama_model)
        self.digest_service = DigestService(
            self.userbot,
            self.ollama,
            initial_history_limit=settings.initial_history_limit,
        )

    async def close(self) -> None:
        # Бот-клиент запускается отдельно; userbot закрывает собственный клиент.
        if self.bot_telethon.is_connected():
            await self.bot_telethon.disconnect()
        await self.userbot.close()
        await self.database.close()
