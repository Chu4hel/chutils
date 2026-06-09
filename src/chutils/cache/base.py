from abc import ABC, abstractmethod
from typing import Optional, TypeVar, Generic

T = TypeVar("T")


class BaseCacheBackend(ABC, Generic[T]):
    """
    Базовый абстрактный класс для всех бэкендов кэширования.
    
    Определяет единый интерфейс для синхронных и асинхронных операций.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """
        Получить значение из кэша.
        
        Args:
            key (str): Ключ кэша.
            
        Returns:
            Значение или None, если ключ не найден или просрочен.
        """
        pass

    @abstractmethod
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """
        Сохранить значение в кэше.

        Args:
            key (str): Ключ кэша.
            value: Значение для сохранения.
            ttl (Optional[int]): Время жизни в секундах. Если None, используется вечное хранение.
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Удалить ключ из кэша.

        Args:
            key (str): Ключ кэша.
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Проверить наличие ключа в кэше.

        Args:
            key (str): Ключ кэша.

        Returns:
            bool: True, если ключ существует и не просрочен.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Очистить весь кэш."""
        pass

    # --- Асинхронные методы (по умолчанию вызывают синхронные) ---

    async def aget(self, key: str) -> Optional[T]:
        """Асинхронное получение значения."""
        return self.get(key)

    async def aset(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """Асинхронное сохранение значения."""
        self.set(key, value, ttl)

    async def adelete(self, key: str) -> None:
        """Асинхронное удаление значения."""
        self.delete(key)

    async def aexists(self, key: str) -> bool:
        """Асинхронная проверка наличия ключа."""
        return self.exists(key)

    async def aclear(self) -> None:
        """Асинхронная очистка кэша."""
        self.clear()
