import structlog
from telethon import TelegramClient


logger = structlog.get_logger(__name__)


class UserbotAuthService:
    def __init__(self, client: TelegramClient, phone: str) -> None:
        self.client = client
        self.phone = phone

    async def authenticate(self) -> None:
        await self.client.connect()
        if await self.client.is_user_authorized():
            logger.info("Telethon session is authorized")
            return

        logger.info("Telethon login required")
        await self.client.start(
            phone=self.phone,
            code_callback=lambda: input("Код Telegram: "),
            password=lambda: input("Пароль 2FA: "),
        )
