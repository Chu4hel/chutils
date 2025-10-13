import keyring
from keyring.errors import NoKeyringError, PasswordDeleteError
from typing import Optional
from . import logger as logging

logger = logging.setup_logger(__name__)


class SecretManager:
    """
    Универсальный менеджер для безопасного хранения и получения секретов
    с использованием системного хранилища (keyring).

    Изолирует секреты разных приложений по `service_name`.
    """

    prefix: str = "Chutils_"

    def __init__(self, service_name: str) -> None:
        """
        Инициализирует менеджер для конкретного сервиса (приложения).

        :param service_name: Уникальное имя для твоего приложения.
                             Например, 'my_super_app' или 'project_alpha_db'.
        """
        if not service_name or not isinstance(service_name, str):
            raise ValueError("service_name должен быть непустой строкой.")
        self.service_name: str = self.prefix + service_name
        logger.devdebug(f"Менеджер секретов инициализирован для сервиса: '{self.service_name}'")

    def save_secret(self, key: str, value: str) -> bool:
        """
        Сохраняет пару ключ-значение в системном хранилище.
        Если ключ уже существует, его значение будет перезаписано.

        :param key: Ключ для секрета (например, 'db_password' или 'api_token').
        :param value: Секретное значение, которое нужно сохранить.
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

        :param key: Ключ, по которому нужно найти секрет.
        :return: Сохраненное значение или None, если ключ не найден.
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

        :param key: Ключ, который нужно удалить.
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
        Это псевдоним для функции save_secret, так как keyring перезаписывает значение.

        :param key: Ключ для секрета (например, 'db_password' или 'api_token').
        :param value: Секретное значение, которое нужно сохранить.
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
