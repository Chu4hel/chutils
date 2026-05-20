"""
Управление жизненным циклом приложения.

Обеспечивает механизмы регистрации функций очистки (cleanup callbacks), 
которые будут выполнены при завершении работы приложения.
"""

import logging
from typing import Callable, List, Union, Any, Awaitable

logger = logging.getLogger(__name__)

# Тип для функций очистки: может быть обычной функцией или корутиной
CleanupCallback = Union[Callable[[], Any], Callable[[], Awaitable[Any]]]


class LifecycleManager:
    """
    Менеджер жизненного цикла, управляющий реестром функций очистки.
    """

    def __init__(self):
        self._cleanup_callbacks: List[CleanupCallback] = []

    def register_cleanup(self, func: CleanupCallback) -> CleanupCallback:
        """
        Регистрирует функцию для выполнения при завершении работы.

        Функции выполняются в порядке LIFO (Last-In-First-Out).
        Поддерживаются как синхронные, так и асинхронные функции.

        Args:
            func: Функция или корутина для регистрации.

        Returns:
            Та же функция (позволяет использовать как декоратор).
        """
        if func not in self._cleanup_callbacks:
            self._cleanup_callbacks.append(func)
            logger.debug("Зарегистрирована функция очистки: %s",
                         func.__name__ if hasattr(func, '__name__') else str(func))
        return func

    def get_cleanup_callbacks(self) -> List[CleanupCallback]:
        """
        Возвращает список зарегистрированных функций в порядке LIFO.
        """
        return list(reversed(self._cleanup_callbacks))

    def _clear_registry(self):
        """
        Очищает реестр (в основном для тестов).
        """
        self._cleanup_callbacks.clear()


# Глобальный экземпляр менеджера
_manager = LifecycleManager()


def register_cleanup(func: CleanupCallback) -> CleanupCallback:
    """
    Публичный API для регистрации функции очистки.

    Пример использования:
    
    @register_cleanup
    async def close_db():
        await db.close()
        
    def cleanup_logs():
        print("Cleaning up logs...")
    register_cleanup(cleanup_logs)
    """
    return _manager.register_cleanup(func)
