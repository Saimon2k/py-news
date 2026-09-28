import asyncio

import structlog

from src.app.container import AppContainer
from src.app.handlers import create_router
from src.app.settings import load_settings


async def run() -> None:
    settings = load_settings()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(settings.log_level.upper())
    )
    app = AppContainer(settings)
    try:
        await app.database.initialize()
        await app.auth.authenticate()
        await app.userbot.start()
        app.dispatcher.include_router(
            create_router(app.database.sessions, app.digest_service, app.userbot)
        )
        await app.dispatcher.start_polling(app.bot)
    finally:
        await app.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
