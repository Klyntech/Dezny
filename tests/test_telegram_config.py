import pytest

from app.config import Settings


def test_telegram_allowlist_parses_comma_separated_ids() -> None:
    settings = Settings(_env_file=None, telegram_allowed_user_ids="123, 456,123")
    assert settings.allowed_telegram_user_ids == {123, 456}


def test_empty_telegram_allowlist_denies_all_by_default() -> None:
    settings = Settings(_env_file=None, telegram_allowed_user_ids="")
    assert settings.allowed_telegram_user_ids == set()


def test_telegram_allowlist_rejects_non_numeric_ids() -> None:
    settings = Settings(_env_file=None, telegram_allowed_user_ids="123,not-an-id")
    with pytest.raises(ValueError, match="comma-separated integers"):
        _ = settings.allowed_telegram_user_ids
