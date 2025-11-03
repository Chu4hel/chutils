import keyring
from keyring.errors import NoKeyringError, PasswordDeleteError
from typing import Optional
from . import logger as logging

logger = logging.setup_logger(__name__)


class SecretManager:
    """
    Универсальный менеджер для безопасного хранения и получения секретов
    с использованием системного хранилища (keyring).

    Использует системное хранилище (keyring) для безопасного хранения данных.
    Изолирует секреты разных приложений с помощью префикса и `service_name`.

    Attributes:
        service_name (str): Полное имя сервиса, используемое в keyring.
    """

    prefix: str = "Chutils_"

    def __init__(self, service_name: str, prefix: str = "Chutils_") -> None:
        """Инициализирует менеджер для конкретного сервиса (приложения).

        Args:
            service_name: Уникальное имя для вашего приложения, например,
                'my_super_app' или 'project_alpha_db'.
            prefix: Опциональный префикс для имени сервиса. По умолчанию
                используется "Chutils_", чтобы избежать конфликтов с другими
                приложениями. Можно передать пустую строку, чтобы
                использовать `service_name` без префикса.

        Raises:
            ValueError: Если `service_name` является пустой строкой.
        """
        if not service_name or not isinstance(service_name, str):
            raise ValueError("service_name должен быть непустой строкой.")
        self.service_name: str = prefix + service_name
        logger.devdebug(f"Менеджер секретов инициализирован для сервиса: '{self.service_name}'")

    def save_secret(self, key: str, value: str) -> bool:
        """
        Сохраняет пару ключ-значение в системном хранилище.
        Если ключ уже существует, его значение будет перезаписано.

        Args:
            key: Ключ для секрета (например, 'db_password' или 'api_token').
            value: Секретное значение, которое нужно сохранить.

        Returns:
            True: Если секрет успешно сохранен.
            False: Если произошла ошибка.
        """
        try:
            keyring.set_password(self.service_name, key, value)
            logger.devdebug(f"Секрет для ключа '{key}' успешно сохранен.")
            return True
        except NoKeyringError:
            logger.error("Ошибка: системное хранилище (keyring) не найдено. Секрет не сохранен.")
            return False
        except Exception as e:
            logger.error(f"Произошла непредвиденная ошибка при сохранении секрета: {e}")
            return False

    def get_secret(self, key: str) -> Optional[str]:
        """
        Получает секретное значение по ключу из системного хранилища.

        Args:
            key: Ключ, по которому нужно найти секрет.

        Returns:
            value (str): Сохраненное значение
            None (None): Если ключ не найден или произошла ошибка.
        """
        try:
            value = keyring.get_password(self.service_name, key)
            if value is None:
                logger.devdebug(f"Секрет для ключа '{key}' не найден.")
            else:
                logger.devdebug(f"Секрет для ключа '{key}' получен.")
            return value
        except NoKeyringError:
            logger.critical("Ошибка: системное хранилище (keyring) не найдено. Невозможно получить секрет.")
            return None
        except Exception as e:
            logger.error(f"Произошла непредвиденная ошибка при получении секрета: {e}")
            return None

    def delete_secret(self, key: str) -> bool:
        """
        Удаляет пару ключ-значение из системного хранилища.

        Args:
            key: Ключ секрета, который нужно удалить.

        Returns:
            True, если секрет был удален или уже не существовал.
            False, если произошла ошибка при удалении.
        """
        try:
            # Сначала проверим, есть ли что удалять, для более понятного вывода
            if self.get_secret(key) is None:
                # Сообщение об отсутствии секрета уже будет выведено из get_secret
                return True

            keyring.delete_password(self.service_name, key)
            logger.devdebug(f"Секрет для ключа '{key}' успешно удален.")
            return True
        except PasswordDeleteError:
            logger.error(f"Ошибка: не удалось удалить секрет для ключа '{key}'.")
            return False
        except NoKeyringError:
            logger.critical("Ошибка: системное хранилище (keyring) не найдено. Невозможно удалить секрет.")
            return False
        except Exception as e:
            logger.error(f"Произошла непредвиденная ошибка при удалении секрета: {e}")
            return False

    def update_secret(self, key: str, value: str) -> bool:
        """
        Обновляет значение для существующего ключа.
        Это псевдоним для функции `save_secret`,
            так как `keyring` по умолчанию перезаписывает значение при сохранении.

        Args:
            key: Ключ для секрета (например, 'db_password' или 'api_token').
            value: Новое секретное значение.

        Returns:
            True: Если секрет успешно обновлен.
            False: В случае возникновения ошибки.
        """
        logger.devdebug(f"Обновление секрета для ключа '{key}'...")
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
