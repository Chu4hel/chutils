from abc import ABC, abstractmethod


class SecretProvider(ABC):
    """
    Абстрактный базовый класс для провайдеров секретов.
    Определяет интерфейс стратегии для различных механизмов хранения.
    """

    @abstractmethod
    def get(self, key: str, service_name: str) -> str | None:
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
