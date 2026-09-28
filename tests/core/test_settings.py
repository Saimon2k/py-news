import pytest

from src.app.settings import load_settings


def test_settings_require_real_telegram_credentials(tmp_path) -> None:
    (tmp_path / "config.toml").write_text(
        '[default]\nOllama = { Url = "http://localhost:11434", Model = "llama3" }\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="настройки Telegram"):
        load_settings(tmp_path)


def test_settings_load_secrets_and_nested_configuration(tmp_path) -> None:
    (tmp_path / "config.toml").write_text(
        '[default]\nStorage = { DatabasePath = "sqlite+aiosqlite:///./test.db" }\n'
        'Ollama = { Url = "http://ollama:11434", Model = "qwen" }\n',
        encoding="utf-8",
    )
    (tmp_path / ".secrets.toml").write_text(
        '[default.Telegram]\nApiId = 123\nApiHash = "hash"\n'
        'PhoneNumber = "+70000000000"\nBotToken = "token"\n'
        'Proxy = "tg://proxy?server=proxy.example&port=1080&secret=0123456789abcdef0123456789abcdef"\n',
        encoding="utf-8",
    )

    settings = load_settings(tmp_path)

    assert settings.telegram_api_id == 123
    assert settings.ollama_model == "qwen"
    assert settings.database_url.endswith("test.db")
    assert settings.telegram_proxy == (
        "proxy.example", 1080, "0123456789abcdef0123456789abcdef"
    )


def test_settings_reject_invalid_proxy_url(tmp_path) -> None:
    (tmp_path / ".secrets.toml").write_text(
        '[default.Telegram]\nApiId = 123\nApiHash = "hash"\n'
        'PhoneNumber = "+70000000000"\nBotToken = "token"\nProxy = "http://invalid"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tg://proxy"):
        load_settings(tmp_path)
