import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, TYPE_CHECKING

import keyring
from dotenv import load_dotenv
from keyring.errors import NoKeyringError, PasswordDeleteError

from .. import config

if TYPE_CHECKING:
    from ..logger import ChutilsLogger

# Ленивая инициализация логгера модуля
_module_logger: Optional['ChutilsLogger'] = None


def _get_logger() -> 'ChutilsLogger':
    """
    Получает лениво инициализированный логгер модуля.

    Returns:
        Экземпляр ChutilsLogger.
    """
    global _module_logger
    if _module_logger is None:
        from .. import logger as chutils_logger
        _module_logger = chutils_logger.setup_logger(__name__)
    return _module_logger  # type: ignore


class SecretProvider(ABC):
    """
    Абстрактный базовый класс для провайдеров секретов.
    Определяет интерфейс стратегии для различных механизмов хранения.
    """

    @abstractmethod
    def get(self, key: str, service_name: str) -> Optional[str]:
        """
        Получить значение секрета по ключу.

        Args:
            key: Имя секрета.
            service_name: Имя сервиса (используется для изоляции в хранилищах типа keyring).

        Returns:
            Значение секрета или None, если секрет не найден.
        """
        pass

    @abstractmethod
    def set(self, key: str, value: str, service_name: str) -> bool:
        """
        Сохранить значение секрета.

        Args:
            key: Имя секрета.
            value: Значение секрета.
            service_name: Имя сервиса.

        Returns:
            True, если сохранение прошло успешно, иначе False.
        """
        pass

    @abstractmethod
    def delete(self, key: str, service_name: str) -> bool:
        """
        Удалить секрет.

        Args:
            key: Имя секрета.
            service_name: Имя сервиса.

        Returns:
            True, если удаление прошло успешно, иначе False.
        """
        pass


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

    def get(self, key: str, service_name: str) -> Optional[str]:
        """
        Получает пароль из системного хранилища.
        """
        if self.disabled:
            _get_logger().devdebug("Keyring отключен. Поиск секрета '%s' пропущен.", key)
            return None

        try:
            value = keyring.get_password(service_name, key)
            if value is not None:
                _get_logger().devdebug("Секрет '%s' получен из keyring (сервис: %s).", key, service_name)
            return value
        except NoKeyringError:
            _get_logger().warning("Keyring не доступен. Поиск только в окружении.")
            return None
        except Exception as e:
            _get_logger().error("Ошибка при получении секрета из keyring: %s", e)
            return None

    def set(self, key: str, value: str, service_name: str) -> bool:
        """
        Сохраняет пароль в системное хранилище.
        """
        if self.disabled:
            _get_logger().devdebug("Keyring отключен. Секрет '%s' не будет сохранен.", key)
            return False

        try:
            keyring.set_password(service_name, key, value)
            _get_logger().devdebug("Секрет для ключа '%s' сохранен в keyring (сервис: %s).", key, service_name)
            return True
        except NoKeyringError:
            _get_logger().error("Системное хранилище (keyring) не найдено.")
            return False
        except Exception as e:
            _get_logger().error("Ошибка при сохранении секрета в keyring: %s", e)
            return False

    def delete(self, key: str, service_name: str) -> bool:
        """
        Удаляет пароль из системного хранилища.
        """
        if self.disabled:
            return True

        try:
            if keyring.get_password(service_name, key) is None:
                return True

            keyring.delete_password(service_name, key)
            _get_logger().devdebug("Секрет '%s' удален из keyring (сервис: %s).", key, service_name)
            return True
        except PasswordDeleteError:
            _get_logger().error("Не удалось удалить секрет '%s' из keyring.", key)
            return False
        except NoKeyringError:
            return False
        except Exception as e:
            _get_logger().error("Ошибка при удалении секрета из keyring: %s", e)
            return False


class DotEnvProvider(SecretProvider):
    """
    Провайдер для работы с .env файлами.
    Обеспечивает загрузку переменных окружения из файла при первом обращении.
    """

    def __init__(self, dotenv_path: Optional[str] = None):
        """
        Инициализирует провайдер.

        Args:
            dotenv_path: Явный путь к .env файлу. Если не указан, ищется в корне проекта.
        """
        self.dotenv_path = dotenv_path
        self._loaded = False
        self._values: Dict[str, str] = {}

    def _load_if_needed(self):
        """
        Загружает переменные из .env файла, если это еще не было сделано.
        """
        if self._loaded:
            return

        path = self.dotenv_path
        if not path:
            base_dir = config.get_base_dir()
            if base_dir:
                path = os.path.join(base_dir, '.env')

        if path and os.path.exists(path):
            load_dotenv(dotenv_path=path, override=False)
            _get_logger().debug("Найден и загружен .env файл: %s", path)

        # Кэшируем текущие переменные окружения
        self._values = dict(os.environ)
        self._loaded = True

    def get(self, key: str, service_name: str) -> Optional[str]:
        """
        Получает значение из загруженных .env данных.
        """
        self._load_if_needed()
        value = self._values.get(key)
        if value is not None:
            _get_logger().devdebug("Секрет '%s' найден в .env файле.", key)
        return value

    def set(self, key: str, value: str, service_name: str) -> bool:
        """
        DotEnvProvider не поддерживает сохранение (доступен только для чтения).
        """
        _get_logger().warning("DotEnvProvider не поддерживает сохранение секретов.")
        return False

    def delete(self, key: str, service_name: str) -> bool:
        """
        DotEnvProvider не поддерживает удаление.
        """
        _get_logger().warning("DotEnvProvider не поддерживает удаление секретов.")
        return False


class EnvProvider(SecretProvider):
    """
    Провайдер для работы с переменными окружения ОС (os.environ).
    """

    def get(self, key: str, service_name: str) -> Optional[str]:
        """
        Получает значение из переменных окружения ОС.
        """
        value = os.environ.get(key)
        if value is not None:
            _get_logger().devdebug("Секрет '%s' найден в переменных окружения.", key)
        return value

    def set(self, key: str, value: str, service_name: str) -> bool:
        """
        EnvProvider не поддерживает сохранение.
        """
        _get_logger().warning("EnvProvider не поддерживает сохранение секретов.")
        return False

    def delete(self, key: str, service_name: str) -> bool:
        """
        EnvProvider не поддерживает удаление.
        """
        _get_logger().warning("EnvProvider не поддерживает удаление секретов.")
        return False
