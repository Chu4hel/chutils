"""
Провайдер секретов для GCP Secret Manager.
"""
from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
import os
from typing import Any, cast

from chutils.exceptions import OptionalDependencyError
from .base import SecretProvider

logger = logging.getLogger("chutils.secret_manager.providers.gcp")


class GCPSecretManagerProvider(SecretProvider):
    """Провайдер секретов для интеграции с GCP Secret Manager.

    Использует официальный SDK google-cloud-secret-manager.
    """

    def __init__(self, project_id: str | None = None, **kwargs: Any) -> None:
        """Инициализирует GCPSecretManagerProvider.

        Args:
            project_id: Идентификатор проекта Google Cloud. Если не передан,
                        будет автоматически считан из переменных окружения
                        GOOGLE_CLOUD_PROJECT или GCP_PROJECT.
            **kwargs: Дополнительные параметры для инициализации SecretManagerServiceClient.
        """
        self._project_id = project_id
        self.kwargs = kwargs
        self._client: Any = None

    @property
    def project_id(self) -> str:
        """Возвращает project_id (считывает из окружения, если не задан)."""
        if self._project_id is not None:
            return self._project_id

        project = (
            os.environ.get("GOOGLE_CLOUD_PROJECT")  # chutils: ignore[ChutilsIntegrationRule]
            or os.environ.get("GCP_PROJECT")  # chutils: ignore[ChutilsIntegrationRule]
        )
        if not project:
            raise ValueError(
                "Идентификатор проекта Google Cloud (project_id) не задан. "
                "Передайте его в конструктор или установите переменную окружения GOOGLE_CLOUD_PROJECT."
            )
        return project

    def _get_client(self) -> Any:
        """Лениво инициализирует и возвращает клиент SecretManagerServiceClient.

        Raises:
            OptionalDependencyError: Если библиотека google-cloud-secret-manager не установлена.
        """
        if self._client is not None:
            return self._client

        try:
            from google.cloud import secretmanager
        except ImportError:
            raise OptionalDependencyError(
                "Библиотека 'google-cloud-secret-manager' обязательна для GCPSecretManagerProvider. "
                "Установите её через 'pip install google-cloud-secret-manager' или 'pip install chutils[gcp]'."
            )

        self._client = secretmanager.SecretManagerServiceClient(**self.kwargs)
        return self._client

    def get(self, key: str, service_name: str) -> str | None:
        """Получает секрет из GCP Secret Manager.

        Args:
            key: Имя секрета.
            service_name: Имя сервиса.

        Returns:
            Значение секрета или None, если секрет не найден.
        """
        client = self._get_client()
        # Заменяем запрещенные символы в имени секрета
        secret_name = f"{service_name}_{key}".replace("/", "_")
        name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
        try:
            response = client.access_secret_version(request={"name": name})
            return cast(str, response.payload.data.decode("UTF-8"))
        except Exception as e:
            try:
                from google.api_core.exceptions import NotFound
                if isinstance(e, NotFound):
                    logger.debug("Секрет %s не найден в GCP Secret Manager.", secret_name)
                    return None
            except ImportError:
                pass

            logger.warning("Ошибка при получении секрета %s из GCP Secret Manager: %s", secret_name, e)
            return None

    def set(self, key: str, value: str, service_name: str) -> bool:
        """Сохраняет секрет в GCP Secret Manager.

        Args:
            key: Имя секрета.
            value: Значение секрета.
            service_name: Имя сервиса.

        Returns:
            True, если сохранение успешно, иначе False.
        """
        client = self._get_client()
        secret_name = f"{service_name}_{key}".replace("/", "_")
        parent = f"projects/{self.project_id}"
        secret_path = f"{parent}/secrets/{secret_name}"

        # 1. Проверяем существование секрета. Если нет — создаем его.
        try:
            client.get_secret(request={"name": secret_path})
        except Exception as e:
            try:
                from google.api_core.exceptions import NotFound
                is_not_found = isinstance(e, NotFound)
            except ImportError:
                is_not_found = False

            if is_not_found:
                try:
                    client.create_secret(
                        request={
                            "parent": parent,
                            "secret_id": secret_name,
                            "secret": {"replication": {"automatic": {}}},
                        }
                    )
                except Exception as ex:
                    logger.error("Не удалось создать секрет %s в GCP Secret Manager: %s", secret_name, ex)
                    return False
            else:
                logger.error("Ошибка при проверке секрета %s в GCP Secret Manager: %s", secret_name, e)
                return False

        # 2. Добавляем новую версию секрета
        try:
            payload = {"data": value.encode("UTF-8")}
            client.add_secret_version(request={"parent": secret_path, "payload": payload})
            return True
        except Exception as e:
            logger.error("Не удалось добавить версию секрета %s в GCP Secret Manager: %s", secret_name, e)
            return False

    def delete(self, key: str, service_name: str) -> bool:
        """Удаляет секрет из GCP Secret Manager.

        Args:
            key: Имя секрета.
            service_name: Имя сервиса.

        Returns:
            True, если удаление успешно, иначе False.
        """
        client = self._get_client()
        secret_name = f"{service_name}_{key}".replace("/", "_")
        secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
        try:
            client.delete_secret(request={"name": secret_path})
            return True
        except Exception as e:
            logger.error("Не удалось удалить секрет %s из GCP Secret Manager: %s", secret_name, e)
            return False
