# PyNews Digest Bot

Асинхронный сервис собирает сообщения из Telegram-каналов через Telethon, удаляет точные дубли, фильтрует рекламные публикации и смысловые повторы через Ollama, а затем позволяет читать результат в Telegram-боте.

## Требования

- Python 3.11+
- Telegram API ID/hash и телефон аккаунта для Telethon
- токен Telegram Bot API
- Ollama с загруженной моделью (по умолчанию `llama3`)

Установите зависимости: `python -m pip install -r requirements.txt`

## Настройка

Создайте `.secrets.toml` (он исключён из Git):

```toml
[default.Telegram]
ApiId = 123456
ApiHash = "ваш_api_hash"
PhoneNumber = "+79990000000"
BotToken = "токен_бота"
SessionPath = "./storage/telegram"
```

Основные параметры Ollama и SQLite находятся в `config.toml`. Их также можно переопределить переменными окружения `PYNEWS_DATABASE_URL`, `PYNEWS_OLLAMA_URL`, `PYNEWS_OLLAMA_MODEL`, `PYNEWS_TELEGRAM_API_ID`, `PYNEWS_TELEGRAM_API_HASH`, `PYNEWS_TELEGRAM_PHONE` и `PYNEWS_TELEGRAM_BOT_TOKEN`.

Для MTProto-прокси можно добавить в секцию `[default.Telegram]` ключ `Proxy` со ссылкой вида `tg://proxy?server=host&port=443&secret=...` или задать `PYNEWS_TELEGRAM_PROXY`. Приложение использует MTProxy connection mode Telethon, когда этот параметр задан.

Первый вход Telethon интерактивный и запросит код, а при необходимости — пароль 2FA. Не запускайте сервис с чужой или общей session-файлом.

## База данных и запуск

Примените миграции:

```bash
alembic upgrade head
```

Запустите приложение:

```bash
python -m src.main
```

Команды бота: `/start`, `/add <канал>`, `/list`, `/remove <канал>`, `/news`, `/next`.

## Разработка и проверки

```bash
python -m pytest -q
```

`/news` запрашивает новости новее сохранённого состояния канала. `/next` отправляет следующую сохранённую публикацию и отмечает её выданной.
