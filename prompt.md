Ниже представлен перенос архитектуры вашего новостного дайджест-сервиса на стек Python 3.11+.
Вместо .NET Generic Host используется AsyncIO совместно с Dependency Injector для явного DI и слоев. Вместо WTelegram и используются Telethon (для юзербота) и AIOGram (для бот-интерфейса), так как они идеально работают в едином асинхронном цикле событий. База данных реализована на SQLAlchemy 2.0 + Aisqlite с миграциями через Alembic.
------------------------------
## 📂 СТРУКТУРА ПРОЕКТА
Для сохранения чистой архитектуры и явных слоев (Core, Infrastructure, App) проект разделен на пакеты внутри единого репозитория:

news_digest_service/
│
├── .gitignore
├── README.md
├── requirements.txt
├── config.toml               # Конфигурация приложения
├── .secrets.toml             # Локальные секреты (аналог User Secrets)
├── alembic.ini               # Конфигурация миграций БД
│
├── src/
│   ├── __init__.py
│   ├── main.py               # Точка входа (Инициализация контейнера, запуск хоста)
│   │
│   ├── app/                  # Слои запуска, Хост, DI-Контейнер
│   │   ├── __init__.py
│   │   ├── container.py      # Declarative IoC Container
│   │   └── host.py           # Реализация Application Host (аналог Generic Host)
│   │
│   ├── core/                 # Бизнес-логика, Интерфейсы, Доменные модели
│   │   ├── __init__.py
│   │   ├── models.py         # Dataclasses / Доменные сущности
│   │   ├── services/
│   │   │   ├── digest.py     # Обработка LLM, фильтрация
│   │   │   ├── queue.py      # Управление очередью пользователя
│   │   │   └── collector.py  # Бизнес-логика нормализации и дедупликации
│   │   └── interfaces/       # Абстрактные классы (протоколы) для инфры
│   │       ├── repositories.py
│   │       ├── clients.py
│   │       └── services.py
│   │
│   └── infrastructure/       # Реализация внешних интеграций
│       ├── __init__.py
│       ├── database/         # SQLAlchemy, Models, Repositories, Сессии
│       │   ├── models.py
│       │   ├── repositories.py
│       │   └── session.py
│       ├── telegram/         # Реализация Бота (Aiogram) и Юзербота (Telethon)
│       │   ├── bot_service.py
│       │   ├── userbot_client.py
│       │   └── auth_service.py
│       └── ai/               # Реализация Ollama Client (Async Ollama API)
│           └── ollama_client.py
│
└── tests/                    # Модульные и интеграционные тесты
    ├── __init__.py
    ├── conftest.py
    ├── test_normalization.py
    ├── test_deduplication.py
    └── test_llm_parsing.py

------------------------------
## 🛠️ КОД ПРИЛОЖЕНИЯ## 1. Зависимости (requirements.txt)

aiogram>=3.13.0
telethon>=1.36.0
ollama>=0.3.3
sqlalchemy>=2.0.35
aiosqlite>=0.20.0
alembic>=1.13.3
dependency-injector>=4.41.0
dynaconf>=3.2.6
pydantic>=2.9.2
structlog>=24.3.0
pytest>=8.3.3
pytest-asyncio>=0.24.0

## 2. Конфигурация (config.toml и .secrets.toml)
Используем библиотеку Dynaconf — она позволяет разделять базовые настройки и секреты (как User Secrets в .NET).
config.toml:

[default]
Ollama = { Url = "http://localhost:11434", Model = "llama3" }
Storage = { DatabasePath = "sqlite+aiosqlite:///news_digest.db", BatchDirectory = "./storage/batches" }
Logging = { Level = "INFO" }

.secrets.toml (Добавляется в .gitignore):

[default]
Telegram = { ApiId = 123456, ApiHash = "your_api_hash", PhoneNumber = "+79991112233", BotToken = "12345:ABCDE..." }

## 3. Core: Доменные модели (src/core/models.py)

from datetime import datetimefrom enum import Enumfrom typing import Optional, Listfrom pydantic import BaseModel, Field
class MessageType(str, Enum):
    TEXT = "text"
    MEDIA_WITH_CAPTION = "media_with_caption"
    MEDIA_WITHOUT_TEXT = "media_without_text"
class QueueStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
class User(BaseModel):
    id: Optional[int] = None
    telegram_user_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
class UserChannel(BaseModel):
    id: Optional[int] = None
    user_id: int
    channel_id: int
    channel_username: Optional[str] = None
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
class ChannelState(BaseModel):
    id: Optional[int] = None
    user_id: int
    channel_id: int
    last_digest_date: datetime
    last_message_id: int
class CollectedMessage(BaseModel):
    id: Optional[int] = None
    user_id: int
    channel_id: int
    message_id: int
    date: datetime
    text: Optional[str] = None
    type: MessageType
    normalized_text: Optional[str] = None
    content_hash: Optional[str] = None
    is_canonical: bool = True
    duplicate_of_message_id: Optional[int] = None
class DigestItem(BaseModel):
    id: Optional[int] = None
    digest_queue_id: int
    order_index: int
    channel_id: int
    channel_username: Optional[str] = None
    message_id: int
    message_url: str
    type: MessageType
    preview_text: Optional[str] = None
    reason: Optional[str] = None
    is_sent: bool = False
class DigestQueue(BaseModel):
    id: Optional[int] = None
    user_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: QueueStatus = QueueStatus.ACTIVE
    source_batch_path: str
    items: List[DigestItem] = []

## 4. Core: Интерфейсы (src/core/interfaces/)
Реализуем через typing.Protocol или абстрактные классы для соблюдения инверсии зависимостей.

# src/core/interfaces/repositories.pyfrom typing import Protocol, List, Optionalfrom src.core.models import User, UserChannel, ChannelState, DigestQueue, DigestItem
class IUserRepository(Protocol):
    async def get_by_tg_id(self, tg_id: int) -> Optional[User]: ...
    async def create(self, user: User) -> User: ...
class IUserChannelRepository(Protocol):
    async def get_by_user(self, user_id: int) -> List[UserChannel]: ...
    async def add(self, channel: UserChannel) -> UserChannel: ...
    async def remove(self, user_id: int, channel_id_or_username: str) -> bool: ...
class IChannelStateRepository(Protocol):
    async def get_state(self, user_id: int, channel_id: int) -> Optional[ChannelState]: ...
    async def update_state(self, state: ChannelState) -> None: ...
class IDigestQueueRepository(Protocol):
    async def get_active_queue(self, user_id: int) -> Optional[DigestQueue]: ...
    async def create_queue(self, queue: DigestQueue) -> DigestQueue: ...
    async def mark_item_sent(self, item_id: int) -> None: ...

# src/core/interfaces/clients.pyfrom typing import Protocol, List, Dict, Any, Optionalfrom datetime import datetimefrom src.core.models import CollectedMessage
class IUserbotClient(Protocol):
    async def start(self) -> None: ...
    async def get_history(self, channel_id_or_username: str, offset_date: datetime) -> List[CollectedMessage]: ...
    async def resolve_channel_peer(self, target: str) -> Dict[str, Any]: ...
class IOllamaClient(Protocol):
    async def filter_news(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]: ...

## 5. Infrastructure: Модели БД и Репозитории (src/infrastructure/database/)

# src/infrastructure/database/models.pyfrom datetime import datetimefrom sqlalchemy import Integer, String, DateTime, Boolean, ForeignKey, Enum as SQLEnumfrom sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationshipfrom src.core.models import MessageType, QueueStatus
class Base(DeclarativeBase):
    pass
class DBUser(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class DBUserChannel(Base):
    __tablename__ = "user_channels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    channel_id: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_username: Mapped[str] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class DBChannelState(Base):
    __tablename__ = "channel_states"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    channel_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_digest_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
class DBDigestQueue(Base):
    __tablename__ = "digest_queues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[QueueStatus] = mapped_column(SQLEnum(QueueStatus), default=QueueStatus.ACTIVE)
    source_batch_path: Mapped[str] = mapped_column(String, nullable=False)
    items: Mapped[list["DBDigestItem"]] = relationship("DBDigestItem", back_populates="queue")
class DBDigestItem(Base):
    __tablename__ = "digest_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    digest_queue_id: Mapped[int] = mapped_column(Integer, ForeignKey("digest_queues.id"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_id: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_username: Mapped[str] = mapped_column(String, nullable=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_url: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[MessageType] = mapped_column(SQLEnum(MessageType), nullable=False)
    preview_text: Mapped[str] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(String, nullable=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    queue: Mapped[DBDigestQueue] = relationship("DBDigestQueue", back_populates="items")

Пример реализации Scoped-репозитория (src/infrastructure/database/):

from typing import Optional, Listfrom sqlalchemy.ext.asyncio import AsyncSessionfrom sqlalchemy import selectfrom src.core.interfaces.repositories import IUserChannelRepositoryfrom src.core.models import UserChannelfrom src.infrastructure.database.models import DBUserChannel
class UserChannelRepository(IUserChannelRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user(self, user_id: int) -> List[UserChannel]:
        stmt = select(DBUserChannel).where(DBUserChannel.user_id == user_id)
        result = await self.session.execute(stmt)
        db_channels = result.scalars().all()
        return [
            UserChannel(
                id=c.id, user_id=c.user_id, channel_id=c.channel_id,
                channel_username=c.channel_username, title=c.title, created_at=c.created_at
            ) for c in db_channels
        ]

    async def add(self, channel: UserChannel) -> UserChannel:
        db_channel = DBUserChannel(
            user_id=channel.user_id, channel_id=channel.channel_id,
            channel_username=channel.channel_username, title=channel.title
        )
        self.session.add(db_channel)
        await self.session.flush()
        channel.id = db_channel.id
        return channel

    async def remove(self, user_id: int, channel_id_or_username: str) -> bool:
        # Логика удаления по ID или Юзернейму
        pass

## 6. Infrastructure: Интерактивный Юзербот (src/infrastructure/telegram/)
В отличие от С#, в Python Telethon выполняет авторизацию через цикл client.start(), где можно передать функции обратного вызова для интерактивного ввода.

# src/infrastructure/telegram/auth_service.pyimport asyncioimport structlogfrom telethon import TelegramClient
logger = structlog.get_logger()
class UserbotAuthService:
    def __init__(self, client: TelegramClient, phone: str):
        self.client = client
        self.phone = phone

    async def authenticate(self):
        logger.info("Проверка сессии WTelegram/Telethon...")
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                logger.info("Сессия не найдена. Начинаем интерактивный вход.")
                
                # Функции инпута для консоли
                def code_callback():
                    return input("Введите код, пришедший в Telegram: ")
                
                def password_callback():
                    return input("Введите ваш пароль 2FA: ")

                await self.client.start(
                    phone=self.phone,
                    code_callback=code_callback,
                    password_callback=password_callback
                )
                logger.info("Интерактивный вход успешно завершен.")
            else:
                logger.info("Успешная автоматическая авторизация по файлу сессии.")
        except Exception as e:
            logger.error("Ошибка при инициализации юзербота", error=str(e))

Юзербот-клиент для сбора истории:

# src/infrastructure/telegram/userbot_client.pyfrom datetime import datetimefrom typing import List, Dict, Anyfrom telethon import TelegramClientfrom telethon.tl.types import MessageMediaInputPhoto, MessageMediaDocumentfrom src.core.interfaces.clients import IUserbotClientfrom src.core.models import CollectedMessage, MessageType
class UserbotClient(IUserbotClient):
    def __init__(self, client: TelegramClient):
        self.client = client

    async def start(self) -> None:
        if not self.client.is_connected():
            await self.client.connect()

    async def get_history(self, channel_id_or_username: str, offset_date: datetime) -> List[CollectedMessage]:
        messages = []
        # Telethon принимает ID, линки или юзернеймы напрямую в iter_messages
        async for msg in self.client.iter_messages(channel_id_or_username, offset_date=offset_date, reverse=True):
            # Классификация типов сообщений
            msg_type = MessageType.TEXT
            if msg.media:
                msg_type = MessageType.MEDIA_WITH_CAPTION if msg.message else MessageType.MEDIA_WITHOUT_TEXT

            messages.append(CollectedMessage(
                user_id=0, # Заполняется в сервисе-коллекторе
                channel_id=msg.peer_id.channel_id,
                message_id=msg.id,
                date=msg.date,
                text=msg.message,
                type=msg_type
            ))
        return messages

    async def resolve_channel_peer(self, target: str) -> Dict[str, Any]:
        entity = await self.client.get_input_entity(target)
        full_entity = await self.client.get_entity(entity)
        return {
            "id": full_entity.id,
            "username": getattr(full_entity, "username", None),
            "title": getattr(full_entity, "title", "Unknown")
        }

## 7. Infrastructure: Клиент Ollama (src/infrastructure/ai/ollama_client.py)
Интеграция с локальной LLM с обработкой JSON режима и механизмом единственного ретрая.

import jsonimport ollamaimport structlogfrom typing import List, Dict, Anyfrom src.core.interfaces.clients import IOllamaClient
logger = structlog.get_logger()
class OllamaClient(IOllamaClient):
    def __init__(self, base_url: str, model: str):
        self.client = ollama.AsyncClient(host=base_url)
        self.model = model
        self.system_prompt = (
            "Ты — редактор новостного дайджеста. Ты не выдумываешь новости. "
            "Ты работаешь только с входным JSON. Не пиши никакого текста вокруг структуры JSON."
        )

    async def filter_news(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        user_content = (
            "Ниже JSON-массив новостей. Каждая новость имеет id, channel, date, text, type.\n"
            f"{json.dumps(messages, ensure_ascii=False)}\n\n"
            "Задача:\n"
            "1. Убери рекламу, промо, партнёрские ссылки, приглашения, скам.\n"
            "2. Убери смысловые повторы. Если несколько новостей об одном и том же — оставь одну.\n"
            "Верни СТРОГО JSON формат:\n"
            '{\n  "selected": [{"id": 1, "reason": "текст"}],\n  "ads": [2],\n  "duplicates": [3]\n}'
        )

        for attempt in range(2):
            try:
                response = await self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    options={"format": "json"} # Опционально для моделей поддерживающих JSON-mode
                )
                
                raw_text = response['message']['content']
                return json.loads(raw_text)
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.warn(f"Ошибка парсинга JSON от Ollama на попытке {attempt + 1}", error=str(e))
                if attempt == 1:
                    # Хэндлер Fallback-а: если LLM сломалась — возвращаем всё как валидное
                    return {"selected": [{"id": m["id"], "reason": "Fallback"} for m in messages], "ads": [], "duplicates": []}

## 8. Core: Бизнес-логика Сборщика (src/core/services/collector.py)

import reimport hashlibfrom typing import Listfrom src.core.models import CollectedMessage
class NewsCollectorService:
    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        text = text.lower()
        # Ссылки и emoji очистка
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        text = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def calculate_hash(text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def process_and_deduplicate(self, messages: List[CollectedMessage]) -> List[CollectedMessage]:
        seen_hashes = {}
        processed = []
        
        # Сортируем от ранних к поздним, чтобы канонической была ранняя новость
        for msg in sorted(messages, key=lambda x: x.date):
            if msg.text:
                msg.normalized_text = self.normalize_text(msg.text)
                msg.content_hash = self.calculate_hash(msg.normalized_text)
                
                if msg.content_hash in seen_hashes:
                    msg.is_canonical = False
                    msg.duplicate_of_message_id = seen_hashes[msg.content_hash]
                else:
                    seen_hashes[msg.content_hash] = msg.message_id
            processed.append(msg)
        return processed

## 9. App: DI Контейнер (src/app/container.py)
Реализация IoC контейнера с помощью библиотеки dependency_injector. Обеспечивает инжекцию Singleton и фабрик для создания сессий (Scoped в Python реализуется через контекстные менеджеры сессий).

from dependency_injector import containers, providersfrom dynaconf import Dynaconffrom telethon import TelegramClientfrom aiogram import Bot, Dispatcherfrom src.infrastructure.database.session import AsyncDatabaseSessionManagerfrom src.infrastructure.telegram.auth_service import UserbotAuthServicefrom src.infrastructure.telegram.userbot_client import UserbotClientfrom src.infrastructure.ai.ollama_client import OllamaClientfrom src.core.services.collector import NewsCollectorService
class ApplicationContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Database Session Manager (Управляет фабрикой сессий БД)
    db_manager = providers.Singleton(
        AsyncDatabaseSessionManager,
        db_url=config.Storage.DatabasePath
    )

    # Clients (Singletons)
    telethon_client = providers.Singleton(
        TelegramClient,
        session=config.Telegram.SessionPath,
        api_id=config.Telegram.ApiId,
        api_hash=config.Telegram.ApiHash
    )
    
    userbot_auth_service = providers.Singleton(
        UserbotAuthService,
        client=telethon_client,
        phone=config.Telegram.PhoneNumber
    )
    
    userbot_client = providers.Singleton(
        UserbotClient,
        client=telethon_client
    )

    bot_client = providers.Singleton(
        Bot,
        token=config.Telegram.BotToken
    )
    
    dispatcher = providers.Singleton(Dispatcher)

    ollama_client = providers.Singleton(
        OllamaClient,
        base_url=config.Ollama.Url,
        model=config.Ollama.Model
    )

    # Core Services
    collector_service = providers.Factory(NewsCollectorService)

## 10. App: Хост Приложения (src/app/host.py и src/main.py)
Аналог .NET Generic Host — координирует запуск фоновых задач и жизненный цикл.

# src/app/host.pyimport asyncioimport structlogfrom src.infrastructure.telegram.auth_service import UserbotAuthServicefrom src.app.container import ApplicationContainer
logger = structlog.get_logger()
class ApplicationHost:
    def __init__(self, container: ApplicationContainer):
        self.container = container
        self.bot = container.bot_client()
        self.dp = container.dispatcher()
        self.auth_service = container.userbot_auth_service()

    async def start(self):
        logger.info("Запуск инфраструктуры новостного дайджеста...")
        
        # 1. Авторизация юзербота
        await self.auth_service.authenticate()
        
        # 2. Подключение обработчиков aiogram бота
        # (Инициализируются роутеры бота, логика /news, /next)
        
        # 3. Запуск Polling для Telegram бот-интерфейса
        logger.info("Telegram-бот запущен и готов принимать команды.")
        try:
            await self.dp.start_polling(self.bot)
        finally:
            await self.stop()

    async def stop(self):
        logger.info("Остановка сервисов...")
        db_manager = self.container.db_manager()
        await db_manager.close()
        telethon = self.container.telethon_client()
        await telethon.disconnect()
        logger.info("Сервис остановлен.")

Точка входа src/main.py:

# src/main.pyimport asynciofrom dynaconf import Dynaconffrom src.app.container import ApplicationContainerfrom src.app.host import ApplicationHost
def main():
    # Загрузка настроек Dynaconf из config.toml и .secrets.toml
    settings = Dynaconf(
        settings_files=['config.toml', '.secrets.toml'],
        environments=True,
    )
    
    container = ApplicationContainer()
    container.config.from_dict(settings.as_dict())
    
    host = ApplicationHost(container)
    
    try:
        asyncio.run(host.start())
    except KeyboardInterrupt:
        pass
if __name__ == "__main__":
    main()

------------------------------
## 🧪 ТЕСТЫ (tests/test_normalization.py)
Используем pytest и pytest-asyncio для асинхронного тестирования логики.

import pytestfrom src.core.services.collector import NewsCollectorServicefrom src.core.models import CollectedMessage, MessageTypefrom datetime import datetime
def test_normalization_and_hash():
    collector = NewsCollectorService()
    raw_text = " Привет!! Купите НАШИ слоны по ссылке https://test.com 😊 "
    normalized = collector.normalize_text(raw_text)
    
    assert normalized == "привет купите наши слоны по ссылке"
    
    hash_1 = collector.calculate_hash(normalized)
    hash_2 = collector.calculate_hash("привет купите наши слоны по ссылке")
    assert hash_1 == hash_2
def test_deduplication():
    collector = NewsCollectorService()
    messages = [
        CollectedMessage(user_id=1, channel_id=10, message_id=101, date=datetime(2026, 1, 1, 10, 0), text="Событие А", type=MessageType.TEXT),
        CollectedMessage(user_id=1, channel_id=10, message_id=102, date=datetime(2026, 1, 1, 10, 5), text="Событие А", type=MessageType.TEXT)
    ]
    
    processed = collector.process_and_deduplicate(messages)
    
    assert processed[0].is_canonical is True
    assert processed[1].is_canonical is False
    assert processed[1].duplicate_of_message_id == 101

------------------------------
## 📄 ДОКУМЕНТАЦИЯ (README.md)

# Сервис Дайджеста Новостей (Python Edition)
Асинхронный сервис на базе Python 3.11+, осуществляющий сбор новостей из Telegram-каналов через Юзербот, фильтрацию дубликатов и спама через локальную LLM (Ollama) и выдачу результатов через UI Telegram-бота.
## Первый запуск и настройка### 1. Подготовка окружения и OllamaУбедитесь, что у вас установлена и запущена Ollama. Скачайте нужную модель:```bash
ollama pull llama3
```
### 2. Установка зависимостей```bash
pip install -r requirements.txt
```
### 3. Настройка конфигурации и секретовСоздайте файл `.secrets.toml` в корневой директории проекта (он добавлен в `.gitignore`):
```toml
[default]
Telegram = { ApiId = 123456, ApiHash = "ваш_api_hash", PhoneNumber = "+79991112233", BotToken = "токен_вашего_телеграм_бота" }
```
### 4. Инициализация Базы Данных (Миграции Alembic)```bash
alembic upgrade head
```
### 5. Запуск приложения и первичный логин ЮзерботаЗапустите проект:```bash
python src/main.py
```* **Важно:** При первом запуске в консоли появится интерактивный запрос кода авторизации Telegram. Введите код, отправленный в ваше приложение Telegram. Если на аккаунте активен Two-Factor Authentication (2FA) — введите ваш пароль во втором запросе.* После успешного входа сессия сохранится в файл, указанный в путях конфигурации, и повторный ввод кода при перезапусках не потребуется.
## Команды интерфейса бота* `/start` — Получить инструкцию.
* `/add <@username|ссылка>` — Добавить канал для мониторинга.
* `/list` — Вывести список ваших каналов.
* `/news` — Запустить сбор новостей, убрать дубли и сформировать очередь LLM.
* `/next` — Получить следующую уникальную новость из очереди.
