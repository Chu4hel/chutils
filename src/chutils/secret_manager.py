"""
Модуль для безопасного управления секретами.

Обеспечивает доступ к секретам через системное хранилище (keyring), файлы .env
и переменные окружения ОС с настраиваемыми приоритетами.
"""

import asyncio
import os
from typing import Optional, Dict, TYPE_CHECKING

import keyring
from dotenv import load_dotenv
from keyring.errors import NoKeyringError, PasswordDeleteError

from . import config

if TYPE_CHECKING:
    from .logger import ChutilsLogger

# Ленивая инициализация логгера
_module_logger: Optional['ChutilsLogger'] = None

# Глобальный кэш для переменных из .env и флаг, что они загружены
_dotenv_values: Optional[Dict[str, str]] = None
_dotenv_loaded = False


def _get_logger() -> 'ChutilsLogger':
    """
    Получает лениво инициализированный логгер модуля.

    Returns:
        Экземпляр ChutilsLogger.
    """
    global _module_logger
    if _module_logger is None:
        from . import logger as chutils_logger
        _module_logger = chutils_logger.setup_logger(__name__)
    return _module_logger  # type: ignore


def _load_dotenv_if_needed():
    """
    Загружает переменные из .env файла, если это еще не было сделано.

    Ищет файл .env в корне проекта, используя модуль config для определения путей.
    """
    global _dotenv_values, _dotenv_loaded
    if _dotenv_loaded:
        return

    # Ищем .env файл в корне проекта
    config._initialize_paths()
    base_dir = config._BASE_DIR
    if base_dir:
        dotenv_path = os.path.join(base_dir, '.env')
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path=dotenv_path, override=False)
            _get_logger().debug("Найден и загружен .env файл: %s", dotenv_path)

    # Кэшируем переменные окружения, чтобы не читать их каждый раз
    _dotenv_values = dict(os.environ)
    _dotenv_loaded = True


class SecretManager:
    """
    Универсальный менеджер для безопасного хранения и получения секретов.

    Приоритет получения секрета:
    1. Системное хранилище (keyring).
    2. Переменные из `.env` файла в корне проекта.
    3. Переменные окружения ОС.

    Attributes:
        service_name (str): Полное имя сервиса для keyring.
        disable_keyring (bool): Флаг отключения работы с keyring.
    """

    prefix: str = "Chutils_"

    def __init__(self, service_name: Optional[str] = None, prefix: Optional[str] = None) -> None:
        """
        Инициализирует менеджер и лениво загружает переменные из .env файла.

        Порядок определения `service_name`:
        1. Значение, переданное в конструктор (если оно не пустое).
        2. Значение из конфигурационного файла (секция `Secrets`, ключ `service_name`).
        3. Абсолютный путь к корню проекта (для гарантированной уникальности).

        Args:
            service_name: Опциональное уникальное имя для вашего приложения.
            prefix: Опциональный префикс для `service_name`. Если не указан,
                    будет взят из конфига (ключ `prefix`) или использован "Chutils_".

        Raises:
            ValueError: Если не удалось определить service_name.
        """
        # При первом создании экземпляра SecretManager загружаем .env
        _load_dotenv_if_needed()

        final_service_name = service_name
        if not final_service_name:  # Если не передано или пустая строка
            final_service_name = config.get_config_value('Secrets', 'service_name')

        if not final_service_name:  # Если в конфиге тоже пусто
            # Гарантируем, что пути инициализированы
            config._initialize_paths()
            final_service_name = config._BASE_DIR
            _get_logger().debug(
                "service_name для SecretManager не указан. "
                "Для обеспечения уникальности используется путь к проекту: '%s'",
                final_service_name
            )

        final_prefix = prefix
        if final_prefix is None:
            final_prefix = config.get_config_value('Secrets', 'prefix', fallback=self.prefix)

        if not final_service_name:
            raise ValueError(
                "Не удалось определить service_name. Укажите его в конструкторе, "
                "в файле config.yml или убедитесь, что проект имеет четкую структуру (например, .git или pyproject.toml)."
            )

        self.service_name: str = final_prefix + final_service_name
        self.disable_keyring: bool = config.get_config_boolean('secrets', 'disable_keyring', fallback=False)

        _get_logger().devdebug("Менеджер секретов инициализирован для сервиса: '%s' (disable_keyring=%s)",
                               self.service_name, self.disable_keyring)

    def save_secret(self, key: str, value: str) -> bool:
        """
        Сохраняет пару ключ-значение в системном хранилище (keyring).
        Эта функция не влияет на переменные окружения или .env файлы.

        Args:
            key: Ключ секрета.
            value: Секретное значение.

        Returns:
            True, если секрет успешно сохранен в keyring.
            False, если произошла ошибка.
        """
        if self.disable_keyring:
            _get_logger().devdebug(
                "Keyring отключен. Секрет '%s' не будет сохранен в системное хранилище.", key)
            return False

        try:
            keyring.set_password(self.service_name, key, value)
            _get_logger().devdebug("Секрет для ключа '%s' сохранен в keyring.", key)
            return True
        except NoKeyringError:
            _get_logger().error("Системное хранилище (keyring) не найдено.")
            return False
        except Exception as e:
            _get_logger().error("Ошибка при сохранении секрета: %s", e)
            return False

    async def asave_secret(self, key: str, value: str) -> bool:
        """
        Асинхронная версия save_secret.

        Args:
            key: Ключ секрета.
            value: Секретное значение.

        Returns:
            True, если секрет успешно сохранен в keyring.
            False, если произошла ошибка.
        """
        return await asyncio.to_thread(self.save_secret, key, value)

    def get_secret(self, key: str) -> Optional[str]:
        """
        Получает секретное значение по ключу.

        Поиск происходит в следующем порядке:
        1. Системное хранилище (keyring).
        2. Переменные из `.env` файла / переменные окружения.

        Args:
            key: Ключ секрета.

        Returns:
            Значение секрета или None, если ключ не найден.
        """
        if not self.disable_keyring:
            try:
                value = keyring.get_password(self.service_name, key)
                if value is not None:
                    _get_logger().devdebug("Секрет '%s' получен из keyring.", key)
                    return value
            except NoKeyringError:
                _get_logger().warning("Keyring не доступен. Поиск только в окружении.")
            except Exception as e:
                _get_logger().error("Ошибка при получении секрета из keyring: %s", e)
        else:
            _get_logger().devdebug("Keyring отключен. Поиск секрета '%s' в хранилище пропущен.", key)

        # Если в keyring нет, ищем в .env / переменных окружения
        _get_logger().devdebug("Поиск секрета '%s' в .env и переменных окружения...", key)
        value = _dotenv_values.get(key)

        if value is not None:
            _get_logger().devdebug("Секрет '%s' найден в окружении.", key)
        else:
            _get_logger().devdebug("Секрет '%s' не найден.", key)

        return value

    async def aget_secret(self, key: str) -> Optional[str]:
        """
        Асинхронная версия get_secret.

        Args:
            key: Ключ секрета.

        Returns:
            Значение секрета или None.
        """
        return await asyncio.to_thread(self.get_secret, key)

    def delete_secret(self, key: str) -> bool:
        """
        Удаляет пару ключ-значение из системного хранилища (keyring).
        Эта функция не влияет на переменные окружения или .env файлы.

        Args:
            key: Ключ секрета.

        Returns:
            True если секрет удален или отсутствовал,
            False при ошибке.
        """
        if self.disable_keyring:
            _get_logger().devdebug("Keyring отключен. Удаление секрета '%s' пропущено.", key)
            return True

        try:
            if keyring.get_password(self.service_name, key) is None:
                _get_logger().devdebug("Секрет '%s' не найден в keyring.", key)
                return True

            keyring.delete_password(self.service_name, key)
            _get_logger().devdebug("Секрет '%s' удален из keyring.", key)
            return True
        except PasswordDeleteError:
            _get_logger().error("Не удалось удалить секрет '%s' из keyring.", key)
            return False
        except NoKeyringError:
            _get_logger().warning("Keyring не доступен.")
            return False
        except Exception as e:
            _get_logger().error("Произошла непредвиденная ошибка при удалении секрета из keyring: %s", e)
            return False

    async def adelete_secret(self, key: str) -> bool:
        """
        Асинхронная версия delete_secret.

        Args:
            key: Ключ секрета.

        Returns:
            True, если секрет был удален или уже не существовал.
            False, если произошла ошибка при удалении.
        """
        return await asyncio.to_thread(self.delete_secret, key)

    def update_secret(self, key: str, value: str) -> bool:
        """
        Обновляет значение для существующего ключа в системном хранилище (keyring).
        Это псевдоним для `save_secret`.

        Args:
            key: Ключ секрета.
            value: Новое значение.

        Returns:
            True, если секрет успешно обновлен в keyring.
            False в случае ошибки.
        """
        _get_logger().devdebug("Обновление секрета '%s' в keyring...", key)
        return self.save_secret(key, value)


# --- Пример использования ---
# Этот блок выполнится, только если запустить этот файл напрямую (python secret_manager.py)
if __name__ == '__main__':
    # 1. Создаем экземпляр менеджера для нашего приложения "my_test_project"
    secrets = SecretManager("my_test_project")

    # 2. Определяем ключ для пароля от базы данных
    db_password_key = "postgres_password"

    # 3. Сохраняем пароль
    secrets.save_secret(db_password_key, "MySuperSecretPassword123!")

    # 4. Получаем его обратно
    retrieved_password = secrets.get_secret(db_password_key)
    if retrieved_password:
        print(f"  -> Полученный пароль: {retrieved_password}")

    # 5. Пробуем получить несуществующий ключ
    secrets.get_secret("non_existent_key")

    # 6. Обновляем пароль
    secrets.update_secret(db_password_key, "NewPassword456!")
    retrieved_password_after_update = secrets.get_secret(db_password_key)
    if retrieved_password_after_update:
        print(f"  -> Пароль после обновления: {retrieved_password_after_update}")

    # 7. Удаляем пароль
    secrets.delete_secret(db_password_key)

    # 8. Убеждаемся, что он удален
    secrets.get_secret(db_password_key)
