import asyncio
from typing import Optional, List, TYPE_CHECKING

from chutils.exceptions import SecretError
from .providers import SecretProvider, KeyringProvider, DotEnvProvider, EnvProvider
from .. import config

if TYPE_CHECKING:
    from ..logger import ChutilsLogger

# Ленивая инициализация логгера модуля
_module_logger: Optional['ChutilsLogger'] = None


def _get_logger() -> 'ChutilsLogger':
    """
    Получает лениво инициализированный логгер модуля.
    """
    global _module_logger
    if _module_logger is None:
        from .. import logger as chutils_logger
        _module_logger = chutils_logger.setup_logger(__name__)
    return _module_logger  # type: ignore


class SecretManager:
    """
    Универсальный менеджер для управления секретами через цепочку провайдеров.

    Позволяет получать, сохранять и удалять секреты, используя различные стратегии
    (Keyring, .env, переменные окружения и т.д.).
    """

    prefix: str = "Chutils_"

    def __init__(
            self,
            service_name: Optional[str] = None,
            prefix: Optional[str] = None,
            auto_mask_logs: bool = True,
            providers: Optional[List[SecretProvider]] = None
    ) -> None:
        """
        Инициализирует менеджер секретов.

        Args:
            service_name: Уникальное имя сервиса. Если не указано, определяется автоматически.
            prefix: Префикс для имени сервиса (по умолчанию "Chutils_").
            auto_mask_logs: Если True, полученные секреты будут маскироваться в логах.
            providers: Список провайдеров. Если None, создается стандартная цепочка.

        Raises:
            SecretError: Если не удалось автоматически определить `service_name`.
        """
        self.auto_mask_logs = auto_mask_logs

        # Определение service_name (логика сохранена для обратной совместимости)
        final_service_name = service_name
        if not final_service_name:
            final_service_name = config.get_config_value('Secrets', 'service_name')

        if not final_service_name:
            final_service_name = config.get_base_dir()
            _get_logger().debug(
                "service_name для SecretManager не указан. "
                "Используется путь к проекту: '%s'",
                final_service_name
            )

        final_prefix = prefix
        if final_prefix is None:
            final_prefix = config.get_config_value('Secrets', 'prefix', fallback=self.prefix)

        if not final_service_name:
            raise SecretError("Не удалось определить service_name.")

        self.service_name: str = final_prefix + final_service_name

        # Инициализация провайдеров
        if providers is not None:
            self.providers = providers
        else:
            disable_keyring = config.get_config_boolean('secrets', 'disable_keyring', fallback=False)
            self.providers = [
                KeyringProvider(disable_keyring=disable_keyring),
                DotEnvProvider(),
                EnvProvider()
            ]

        _get_logger().devdebug(
            "SecretManager инициализирован. Сервис: '%s', Провайдеров: %d",
            self.service_name, len(self.providers)
        )

    def add_provider(self, provider: SecretProvider, index: Optional[int] = None) -> None:
        """
        Добавляет новый провайдер в цепочку.

        Args:
            provider: Экземпляр провайдера.
            index: Позиция в списке. Если None, добавляется в конец.
        """
        if index is None:
            self.providers.append(provider)
        else:
            self.providers.insert(index, provider)

    def get_secret(self, key: str) -> Optional[str]:
        """
        Получает секрет, опрашивая провайдеры по порядку.
        """
        for provider in self.providers:
            value = provider.get(key, self.service_name)
            if value is not None:
                if self.auto_mask_logs:
                    _get_logger().add_mask(value)
                return value

        _get_logger().devdebug("Секрет '%s' не найден ни в одном из провайдеров.", key)
        return None

    def save_secret(self, key: str, value: str) -> bool:
        """
        Сохраняет секрет в первом провайдере, поддерживающем запись.
        """
        for provider in self.providers:
            if provider.set(key, value, self.service_name):
                return True
        return False

    def delete_secret(self, key: str) -> bool:
        """
        Удаляет секрет во всех провайдерах, поддерживающих удаление.
        """
        success = False
        for provider in self.providers:
            if provider.delete(key, self.service_name):
                success = True
        return success

    def update_secret(self, key: str, value: str) -> bool:
        """
        Обновляет секрет (псевдоним для save_secret).
        """
        return self.save_secret(key, value)

    # Асинхронные обертки
    async def aget_secret(self, key: str) -> Optional[str]:
        return await asyncio.to_thread(self.get_secret, key)

    async def asave_secret(self, key: str, value: str) -> bool:
        return await asyncio.to_thread(self.save_secret, key, value)

    async def adelete_secret(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete_secret, key)
