"""Тесты безопасного хранилища учетных данных прокси KeyringProxyStorage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from chutils import (
    KeyringProxyStorage,
    ProxySecretStorage,
)
from chutils.scraping.proxy import (
    KeyringProxyStorage as ProxyModuleKeyringStorage,
)
from chutils.scraping.proxy import (
    ProxySecretStorage as ProxyModuleSecretStorage,
)


@pytest.fixture
def mock_secret_manager() -> MagicMock:
    """Мок для SecretManager с простым словарем в памяти."""
    sm = MagicMock()
    storage: dict[str, str] = {}

    def get_secret(key: str) -> str | None:
        return storage.get(key)

    def save_secret(key: str, val: str) -> None:
        storage[key] = val

    def delete_secret(key: str) -> None:
        storage.pop(key, None)

    sm.get_secret.side_effect = get_secret
    sm.save_secret.side_effect = save_secret
    sm.delete_secret.side_effect = delete_secret
    return sm


def test_proxy_storage_init_and_alias() -> None:
    """Проверяет инициализацию и совпадение алиасов."""
    assert ProxySecretStorage is KeyringProxyStorage
    assert ProxyModuleKeyringStorage is KeyringProxyStorage
    assert ProxyModuleSecretStorage is KeyringProxyStorage

    storage = KeyringProxyStorage(service_name="custom_svc", key_prefix="custom_px:")
    assert storage.service_name == "custom_svc"
    assert storage.key_prefix == "custom_px:"


def test_make_key_sanitization() -> None:
    """Проверяет очистку имен профилей при формировании ключа Keyring."""
    storage = KeyringProxyStorage(key_prefix="px:")
    assert storage._make_key("profile-1") == "px:profile-1"
    assert storage._make_key("user_work_12") == "px:user_work_12"
    assert storage._make_key("My Profile #1!@") == "px:MyProfile1"
    assert storage._make_key("   ") == "px:default"


def test_crud_proxy(mock_secret_manager: MagicMock) -> None:
    """Проверяет сохранение, извлечение и удаление прокси."""
    storage = KeyringProxyStorage(secret_manager=mock_secret_manager)

    # 1. Прокси отсутствует
    assert storage.get_proxy("acc_1") is None

    # 2. Сохранение валидного прокси
    proxy_url = "http://john_doe:superSecretP@ss@192.168.1.100:8080"
    success = storage.set_proxy("acc_1", proxy_url)
    assert success
    mock_secret_manager.save_secret.assert_called_with("proxy:acc_1", proxy_url)

    # 3. Извлечение
    assert storage.get_proxy("acc_1") == proxy_url

    # 4. Удаление через delete_proxy
    deleted = storage.delete_proxy("acc_1")
    assert deleted
    mock_secret_manager.delete_secret.assert_called_with("proxy:acc_1")
    assert storage.get_proxy("acc_1") is None

    # 5. Удаление при передаче None или пустой строки в set_proxy
    storage.set_proxy("acc_2", proxy_url)
    assert storage.get_proxy("acc_2") == proxy_url
    storage.set_proxy("acc_2", "")
    assert storage.get_proxy("acc_2") is None


def test_masked_proxy_and_mask_helper(mock_secret_manager: MagicMock) -> None:
    """Проверяет получение замаскированного URL и статический хелпер."""
    storage = KeyringProxyStorage(secret_manager=mock_secret_manager)
    full_url = "http://admin:secret123@proxy.provider.com:3128"
    storage.set_proxy("dev_profile", full_url)

    masked = storage.get_masked_proxy("dev_profile")
    assert masked == "http://admin:***@proxy.provider.com:3128"
    assert "secret123" not in str(masked)

    # Проверка mask_proxy_url
    assert KeyringProxyStorage.mask_proxy_url(full_url) == "http://admin:***@proxy.provider.com:3128"
    assert KeyringProxyStorage.mask_proxy_url("socks5://1.2.3.4:1080") == "socks5://1.2.3.4:1080"
    assert KeyringProxyStorage.mask_proxy_url(None) is None


def test_restore_proxy_url(mock_secret_manager: MagicMock) -> None:
    """Проверяет восстановление оригинального пароля из замаскированной строки."""
    storage = KeyringProxyStorage(secret_manager=mock_secret_manager)
    real_url = "http://myuser:P@ssw0rd!@10.0.0.1:8000"
    storage.set_proxy("profile_alpha", real_url)

    # Если передан замаскированный URL
    masked_input = "http://myuser:***@10.0.0.1:8000"
    restored = storage.restore_proxy_url("profile_alpha", masked_input)
    assert restored == real_url
    assert "P@ssw0rd!" in str(restored)

    # Если передан сырой незамаскированный URL — возвращает его же
    other_url = "http://other:pass@10.0.0.2:8000"
    assert storage.restore_proxy_url("profile_alpha", other_url) == other_url

    # Если передан None
    assert storage.restore_proxy_url("profile_alpha", None) is None


def test_sanitize_metadata_dict(mock_secret_manager: MagicMock) -> None:
    """Проверяет санитизацию словаря метаданных перед записью на диск."""
    storage = KeyringProxyStorage(secret_manager=mock_secret_manager)
    meta = {
        "name": "worker_42",
        "proxy": "http://bot_user:TopSecretKey@proxy.net:9090",
        "user_agent": "Mozilla/5.0 ...",
    }

    sanitized = storage.sanitize_metadata_dict("worker_42", meta, sync_to_keyring=True)

    # В словаре пароль должен быть замаскирован
    assert sanitized["proxy"] == "http://bot_user:***@proxy.net:9090"
    assert "TopSecretKey" not in sanitized["proxy"]

    # Исходный словарь не должен мутировать
    assert "TopSecretKey" in meta["proxy"]

    # В Keyring должен быть сохранен оригинальный URL
    assert storage.get_proxy("worker_42") == "http://bot_user:TopSecretKey@proxy.net:9090"


def test_in_memory_fallback_on_keyring_error() -> None:
    """Проверяет in-memory fallback при сбоях системного Keyring."""
    failing_sm = MagicMock()
    failing_sm.save_secret.side_effect = RuntimeError("Keyring locked or unavailable")
    failing_sm.get_secret.side_effect = RuntimeError("Keyring access denied")

    storage = KeyringProxyStorage(secret_manager=failing_sm)
    proxy_url = "http://fallback_user:p@ss@127.0.0.1:8080"

    # Сохранение должно отработать без падения через memory fallback
    assert storage.set_proxy("fallback_acc", proxy_url)
    assert storage.get_proxy("fallback_acc") == proxy_url

    # Удаление
    assert storage.delete_proxy("fallback_acc")
    assert storage.get_proxy("fallback_acc") is None
