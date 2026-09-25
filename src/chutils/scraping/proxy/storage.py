"""Безопасное хранилище учетных данных прокси на базе системного Keyring."""

import logging  # chutils: ignore[ChutilsIntegrationRule]
from typing import Any, ClassVar

from chutils.scraping.proxy.parser import parse_proxy
from chutils.secret_manager import SecretManager

logger = logging.getLogger(__name__)


class KeyringProxyStorage:
    """Безопасное хранилище учетных данных прокси для именованных профилей браузера.

    Обеспечивает разделение публичных метаданных профилей (сохраняемых на диск)
    и приватных паролей прокси. Учетные данные сохраняются в зашифрованном
    системном хранилище ОС (Windows Credential Manager, macOS Keychain, Linux Secret Service)
    через `chutils.SecretManager`, оставляя на диске только замаскированный URL.
    """

    DEFAULT_SERVICE_NAME: str = "chutils_proxy_storage"
    DEFAULT_KEY_PREFIX: str = "proxy:"
    _shared_memory_fallback: ClassVar[dict[str, str]] = {}

    def __init__(
        self,
        service_name: str | None = None,
        key_prefix: str = "proxy:",
        secret_manager: SecretManager | None = None,
    ) -> None:
        """Инициализирует защищенное хранилище прокси.

        Args:
            service_name: Имя сервиса для Keyring (по умолчанию "chutils_proxy_storage").
            key_prefix: Префикс ключей в системном хранилище (по умолчанию "proxy:").
            secret_manager: Пользовательский экземпляр SecretManager (для DI или тестов).
        """
        self.service_name: str = service_name or self.DEFAULT_SERVICE_NAME
        self.key_prefix: str = key_prefix or self.DEFAULT_KEY_PREFIX
        self._secrets: SecretManager = secret_manager or SecretManager(
            service_name=self.service_name,
            auto_mask_logs=True,
        )

    def _make_key(self, profile_name: str) -> str:
        """Формирует изолированный ключ для профиля в Keyring.

        Args:
            profile_name: Имя профиля браузера.

        Returns:
            Строка ключа с префиксом хранилища.
        """
        clean = "".join(c for c in profile_name if c.isalnum() or c in ("-", "_")).strip() or "default"
        return f"{self.key_prefix}{clean}"

    def get_proxy(self, profile_name: str) -> str | None:
        """Получает полный URL прокси с учетными данными для указанного профиля.

        Args:
            profile_name: Имя профиля браузера.

        Returns:
            Полная строка прокси (с паролем) или None, если прокси не привязан.
        """
        key = self._make_key(profile_name)
        try:
            val = self._secrets.get_secret(key)
            if val is not None and val.strip():
                return val.strip()
        except Exception as exc:
            logger.debug("Ошибка получения прокси из Keyring для ключа '%s': %s", key, exc)

        return self._shared_memory_fallback.get(key)

    def set_proxy(self, profile_name: str, proxy_url: str | None) -> bool:
        """Сохраняет или удаляет прокси профиля в безопасном хранилище.

        Args:
            profile_name: Имя профиля браузера.
            proxy_url: Строка прокси (URL или host:port:user:pass) или None для сброса.

        Returns:
            True при успешном сохранении или удалении.
        """
        key = self._make_key(profile_name)
        if not proxy_url or not proxy_url.strip():
            return self.delete_proxy(profile_name)

        clean_url = proxy_url.strip()
        try:
            self._secrets.save_secret(key, clean_url)
        except Exception as exc:
            logger.debug("Не удалось сохранить прокси в Keyring для ключа '%s': %s", key, exc)

        # Синхронизируем in-memory fallback для сред без системного keyring
        self._shared_memory_fallback[key] = clean_url
        return True

    def delete_proxy(self, profile_name: str) -> bool:
        """Удаляет сохраненный прокси профиля из Keyring.

        Args:
            profile_name: Имя профиля браузера.

        Returns:
            True при успешном удалении.
        """
        key = self._make_key(profile_name)
        self._shared_memory_fallback.pop(key, None)
        try:
            self._secrets.delete_secret(key)
        except Exception as exc:
            logger.debug("Ошибка удаления прокси из Keyring для ключа '%s': %s", key, exc)
        return True

    def get_masked_proxy(self, profile_name: str) -> str | None:
        """Получает безопасную замаскированную строку прокси для профиля.

        Args:
            profile_name: Имя профиля браузера.

        Returns:
            Замаскированный URL (например, 'http://user:***@host:port') или None.
        """
        raw = self.get_proxy(profile_name)
        if not raw:
            return None
        return self.mask_proxy_url(raw)

    def restore_proxy_url(self, profile_name: str, proxy_url: str | None) -> str | None:
        """Восстанавливает оригинальный URL с паролем, если передан замаскированный URL.

        Если в переданном URL обнаружена маска '***', метод извлекает
        сохраненный пароль из Keyring для соответствующего профиля.

        Args:
            profile_name: Имя профиля браузера.
            proxy_url: Исходная строка прокси (возможно, замаскированная).

        Returns:
            Полный URL прокси с оригинальным паролем или исходная строка.
        """
        if not proxy_url or not proxy_url.strip():
            return None

        raw = proxy_url.strip()
        if "***" in raw:
            stored = self.get_proxy(profile_name)
            if stored:
                return stored

        return raw

    @staticmethod
    def mask_proxy_url(proxy_url: str | None) -> str | None:
        """Маскирует пароль в строке прокси для безопасного сохранения на диск или логирования.

        Args:
            proxy_url: Строка прокси (URL или параметры).

        Returns:
            Строка со скрытым паролем ('user:***@host:port') или исходное значение.
        """
        if not proxy_url or not proxy_url.strip():
            return None
        try:
            return parse_proxy(proxy_url.strip()).masked_url
        except Exception:
            return proxy_url

    def sanitize_metadata_dict(
        self,
        profile_name: str,
        meta_dict: dict[str, Any],
        proxy_key: str = "proxy",
        sync_to_keyring: bool = True,
    ) -> dict[str, Any]:
        """Санитизирует словарь метаданных профиля перед сохранением в JSON-файл на диске.

        Если в словаре содержится открытый URL с паролем:
        1. Полный URL сохраняется в системный Keyring (если sync_to_keyring=True).
        2. В словаре пароль заменяется на безопасную маску '***'.

        Args:
            profile_name: Имя профиля.
            meta_dict: Исходный словарь метаданных.
            proxy_key: Имя ключа прокси в словаре (по умолчанию 'proxy').
            sync_to_keyring: Сохранить оригинальный прокси в Keyring при наличии пароля.

        Returns:
            Копия словаря с замаскированным прокси.
        """
        res = dict(meta_dict)
        raw_val = res.get(proxy_key)
        if isinstance(raw_val, str) and raw_val.strip():
            clean_val = raw_val.strip()
            if "@" in clean_val and ":" in clean_val and "***" not in clean_val:
                if sync_to_keyring:
                    self.set_proxy(profile_name, clean_val)
                res[proxy_key] = self.mask_proxy_url(clean_val)
        return res


ProxySecretStorage = KeyringProxyStorage
"""Алиас для KeyringProxyStorage."""

__all__ = [
    "KeyringProxyStorage",
    "ProxySecretStorage",
]
