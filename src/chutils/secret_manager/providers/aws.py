"""
Провайдер секретов для AWS Secrets Manager.
"""
from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
from typing import Any, cast

from chutils.exceptions import OptionalDependencyError
from .base import SecretProvider

logger = logging.getLogger("chutils.secret_manager.providers.aws")


class AWSSecretManagerProvider(SecretProvider):
    """Провайдер секретов для интеграции с AWS Secrets Manager.

    Использует библиотеку boto3 для работы с API AWS.
    """

    def __init__(self, region_name: str | None = None, **kwargs: Any) -> None:
        """Инициализирует AWSSecretManagerProvider.

        Args:
            region_name: Название региона AWS (например, 'us-east-1').
            **kwargs: Дополнительные параметры для передачи в boto3.client.
        """
        self.region_name = region_name
        self.kwargs = kwargs
        self._client: Any = None

    def _get_client(self) -> Any:
        """Лениво инициализирует и возвращает клиент boto3.client.

        Raises:
            OptionalDependencyError: Если библиотека boto3 не установлена.
        """
        if self._client is not None:
            return self._client

        try:
            import boto3
        except ImportError:
            raise OptionalDependencyError(
                "Библиотека 'boto3' обязательна для работы AWSSecretManagerProvider. "
                "Установите её через 'pip install boto3' или 'pip install chutils[aws]'."
            )

        self._client = boto3.client("secretsmanager", region_name=self.region_name, **self.kwargs)
        return self._client

    def get(self, key: str, service_name: str) -> str | None:
        """Получает секрет из AWS Secrets Manager.

        Args:
            key: Имя секрета.
            service_name: Имя сервиса.

        Returns:
            Значение секрета или None, если секрет не найден.
        """
        client = self._get_client()
        secret_name = f"{service_name}/{key}"
        try:
            response = client.get_secret_value(SecretId=secret_name)
            return cast(str | None, response.get("SecretString"))
        except Exception as e:
            try:
                from botocore.exceptions import ClientError
                if isinstance(e, ClientError):
                    error_code = e.response.get("Error", {}).get("Code")
                    if error_code in ("ResourceNotFoundException", "AccessDeniedException"):
                        logger.debug("Секрет %s не найден в AWS Secrets Manager: %s", secret_name, e)
                        return None
            except ImportError:
                pass

            logger.warning("Ошибка при получении секрета %s из AWS Secrets Manager: %s", secret_name, e)
            return None

    def set(self, key: str, value: str, service_name: str) -> bool:
        """Сохраняет секрет в AWS Secrets Manager.

        Args:
            key: Имя секрета.
            value: Значение секрета.
            service_name: Имя сервиса.

        Returns:
            True, если сохранение успешно, иначе False.
        """
        client = self._get_client()
        secret_name = f"{service_name}/{key}"
        try:
            client.create_secret(Name=secret_name, SecretString=value)
            return True
        except Exception as e:
            try:
                from botocore.exceptions import ClientError
                if isinstance(e, ClientError):
                    error_code = e.response.get("Error", {}).get("Code")
                    if error_code == "ResourceExistsException":
                        try:
                            client.put_secret_value(SecretId=secret_name, SecretString=value)
                            return True
                        except Exception as ex:
                            logger.error(
                                "Не удалось обновить значение секрета %s в AWS Secrets Manager: %s", secret_name, ex
                            )
                            return False
            except ImportError:
                pass

            logger.error("Не удалось создать секрет %s в AWS Secrets Manager: %s", secret_name, e)
            return False

    def delete(self, key: str, service_name: str) -> bool:
        """Удаляет секрет из AWS Secrets Manager.

        Args:
            key: Имя секрета.
            service_name: Имя сервиса.

        Returns:
            True, если удаление успешно, иначе False.
        """
        client = self._get_client()
        secret_name = f"{service_name}/{key}"
        try:
            client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
            return True
        except Exception as e:
            logger.error("Не удалось удалить секрет %s из AWS Secrets Manager: %s", secret_name, e)
            return False
