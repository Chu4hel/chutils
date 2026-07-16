from __future__ import annotations

from .base import SecretProvider


class KeyringProvider(SecretProvider):
    """
    Провайдер для работы с системным хранилищем (keyring).
    Использует возможности ОС (Windows Credential Locker, macOS Keychain, KWallet/Secret Service).
    """

    def __init__(self, disable_keyring: bool = False):
        """
        Инициализирует провайдер.

        Args:
            disable_keyring: Если True, все операции с keyring будут отключены.
        """
        self.disabled = disable_keyring

    def get(self, key: str, service_name: str) -> str | None:
        """Получает пароль из системного хранилища.

        Args:
            key: Имя запрашиваемого секрета.
            service_name: Имя сервиса/приложения.

        Returns:
            Значение секрета или None, если он не найден.
        """
        from chutils.secret_manager import providers
        if not providers.KEYRING_AVAILABLE:
            from ...exceptions import OptionalDependencyError
            raise OptionalDependencyError(
                "Missing optional dependency: please install chutils[keyring] to use KeyringProvider."
            )

        if self.disabled:
            providers._get_logger().devdebug("Keyring отключен. Поиск секрета '%s' пропущен.", key)
            return None

        try:
            value = providers.keyring.get_password(service_name, key)
            if value is not None:
                providers._get_logger().devdebug("Секрет '%s' получен из keyring (сервис: %s).", key, service_name)
            return value
        except Exception as e:
            # Проверяем по имени класса ошибки, чтобы избежать ImportError
            if type(e).__name__ == "NoKeyringError":
                providers._get_logger().warning("Keyring не доступен. Поиск только в окружении.")
            else:
                providers._get_logger().error("Ошибка при получении секрета из keyring: %s", e)
            return None

    def set(self, key: str, value: str, service_name: str) -> bool:
        """Сохраняет пароль в системное хранилище.

        Args:
            key: Имя секрета.
            value: Сохраняемое значение секрета.
            service_name: Имя сервиса/приложения.

        Returns:
            True, если сохранение успешно, иначе False.
        """
        from chutils.secret_manager import providers
        if not providers.KEYRING_AVAILABLE:
            from ...exceptions import OptionalDependencyError
            raise OptionalDependencyError(
                "Missing optional dependency: please install chutils[keyring] to use KeyringProvider."
            )

        if self.disabled:
            providers._get_logger().devdebug("Keyring отключен. Секрет '%s' не будет сохранен.", key)
            return False

        try:
            providers.keyring.set_password(service_name, key, value)
            providers._get_logger().devdebug("Секрет для ключа '%s' сохранен в keyring (сервис: %s).", key,
                                             service_name)
            return True
        except Exception as e:
            if type(e).__name__ == "NoKeyringError":
                providers._get_logger().error("Системное хранилище (keyring) не найдено.")
            else:
                providers._get_logger().error("Ошибка при сохранении секрета в keyring: %s", e)
            return False

    def delete(self, key: str, service_name: str) -> bool:
        """Удаляет пароль из системного хранилища.

        Args:
            key: Имя удаляемого секрета.
            service_name: Имя сервиса/приложения.

        Returns:
            True, если удаление успешно, иначе False.
        """
        from chutils.secret_manager import providers
        if not providers.KEYRING_AVAILABLE:
            from ...exceptions import OptionalDependencyError
            raise OptionalDependencyError(
                "Missing optional dependency: please install chutils[keyring] to use KeyringProvider."
            )

        if self.disabled:
            return True

        try:
            if providers.keyring.get_password(service_name, key) is None:
                return True

            providers.keyring.delete_password(service_name, key)
            providers._get_logger().devdebug("Секрет '%s' удален из keyring (сервис: %s).", key, service_name)
            return True
        except Exception as e:
            if type(e).__name__ == "PasswordDeleteError":
                providers._get_logger().error("Не удалось удалить секрет '%s' из keyring.", key)
            elif type(e).__name__ == "NoKeyringError":
                pass
            else:
                providers._get_logger().error("Ошибка при удалении секрета из keyring: %s", e)
            return False
