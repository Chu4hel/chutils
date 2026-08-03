"""Тесты хранения и шифрования моделей профилей браузеров."""

import pytest
from chutils.scraping.profiles.models import (
    BrowserProfile,
    CookieData,
    HeaderData,
    StorageData,
)
from chutils.scraping.profiles.storage import (
    load_profile_from_file,
    save_profile_to_file,
)


def test_browser_profile_serialization():
    profile = BrowserProfile(
        engine_origin="nodriver",
        cookies=[
            CookieData(name="session_id", value="xyz123", domain="example.com", secure=True)
        ],
        storage=StorageData(
            local_storage={"https://example.com": {"theme": "dark"}}
        ),
        headers=HeaderData(user_agent="Mozilla/5.0 CustomUA"),
    )

    json_data = profile.model_dump_json()
    assert "xyz123" in json_data
    assert "example.com" in json_data

    restored = BrowserProfile.model_validate_json(json_data)
    assert restored.engine_origin == "nodriver"
    assert len(restored.cookies) == 1
    assert restored.cookies[0].name == "session_id"
    assert restored.storage.local_storage["https://example.com"]["theme"] == "dark"


def test_save_and_load_chprofile(tmp_path):
    profile = BrowserProfile(
        engine_origin="playwright",
        cookies=[CookieData(name="auth", value="token123", domain=".test.org")],
    )

    file_path = tmp_path / "my_session.chprofile"
    saved_path = save_profile_to_file(profile, file_path)

    assert saved_path.exists()
    assert saved_path.suffix == ".chprofile"

    loaded = load_profile_from_file(saved_path)
    assert loaded.engine_origin == "playwright"
    assert loaded.cookies[0].value == "token123"


def test_save_and_load_encrypted_chprofile(tmp_path):
    profile = BrowserProfile(
        engine_origin="selenium",
        cookies=[CookieData(name="secret_key", value="supersecret", domain="bank.com")],
    )

    file_path = tmp_path / "secret.chprofile"
    password = "MyStrongPassword123!"

    saved_path = save_profile_to_file(profile, file_path, password=password)
    assert saved_path.exists()

    # Попытка открыть без пароля должна вызвать ошибку
    with pytest.raises(Exception):
        load_profile_from_file(saved_path)

    # Загрузка с правильным паролем
    loaded = load_profile_from_file(saved_path, password=password)
    assert loaded.engine_origin == "selenium"
    assert loaded.cookies[0].value == "supersecret"
