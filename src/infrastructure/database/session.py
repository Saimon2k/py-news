from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import delete, text

from src.infrastructure.database.models import Base, DBDigestItem, DBDigestQueue


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        async with self.sessions.begin() as session:
            await session.execute(delete(DBDigestItem))
            await session.execute(delete(DBDigestQueue))

    async def close(self) -> None:
        await self.engine.dispose()
