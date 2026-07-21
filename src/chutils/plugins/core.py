from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
from typing import Any

logger = logging.getLogger("chutils.plugins")


class PluginError(Exception):
    """Базовое исключение для ошибок системы плагинов."""
    pass


class PluginRegistry:
    """
    Реестр плагинов chutils.
    Управляет жизненным циклом, регистрацией и автообнаружением плагинов.
    """
    _instance: PluginRegistry | None = None
    _initialized: bool = False

    def __new__(cls) -> PluginRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Инициализирует PluginRegistry."""
        if self._initialized:
            return
        self._plugins: dict[str, Any] = {}
        self._loaded_groups: set[str] = set()
        self._initialized = True

    def clear(self) -> None:
        """Очистить все зарегистрированные плагины (в основном для тестов)."""
        self._plugins.clear()
        self._loaded_groups.clear()

    def register(self, plugin: Any) -> None:
        """Явно зарегистрировать плагин.
        Плагин должен иметь атрибут name.

        Args:
            plugin: Объект или класс регистрируемого плагина.
        """
        if not hasattr(plugin, "name") or not plugin.name:
            raise PluginError("Плагин должен иметь непустой атрибут 'name'.")

        name = plugin.name
        if name in self._plugins:
            logger.warning("Плагин '%s' уже зарегистрирован и будет перезаписан.", name)

        self._plugins[name] = plugin
        logger.debug("Плагин '%s' успешно зарегистрирован.", name)

    def get_plugin(self, name: str) -> Any | None:
        """Получить зарегистрированный плагин по имени.

        Args:
            name: Имя плагина.

        Returns:
            Экземпляр плагина или None, если он не найден.
        """
        return self._plugins.get(name)

    def get_all_plugins(self) -> list[Any]:
        """Получить список всех зарегистрированных плагинов.

        Returns:
            Список всех зарегистрированных плагинов.
        """
        return list(self._plugins.values())

    def get_plugins_by_type(self, plugin_type: type[Any]) -> list[Any]:
        """Получить все плагины, которые являются экземплярами или наследниками указанного типа.

        Args:
            plugin_type: Класс/тип плагина для фильтрации.

        Returns:
            Список плагинов, соответствующих указанному типу.
        """
        result = []
        for plugin in self._plugins.values():
            # Если плагин зарегистрирован как класс
            if isinstance(plugin, type) and issubclass(plugin, plugin_type):
                result.append(plugin)
            # Если плагин зарегистрирован как инстанс
            elif isinstance(plugin, plugin_type):
                result.append(plugin)
        return result

    def discover_plugins(self, group: str = "chutils.plugins") -> None:
        """Автоматическое обнаружение плагинов через Python entry_points.
        Исключения при загрузке плагина логируются, но не прерывают работу всей системы.

        Args:
            group: Имя группы entry points для поиска плагинов.
        """
        if group in self._loaded_groups:
            return

        logger.debug("Запуск автообнаружения плагинов для группы '%s'...", group)

        from importlib.metadata import entry_points
        eps = entry_points(group=group)

        for ep in eps:
            try:
                # Загружаем плагин лениво
                plugin_class = ep.load()
                # Инстанцируем или регистрируем класс
                if isinstance(plugin_class, type):
                    plugin_instance = plugin_class()
                else:
                    plugin_instance = plugin_class

                self.register(plugin_instance)
            except Exception as e:
                logger.error(
                    "Не удалось загрузить плагин '%s' из entry_point '%s': %s",
                    ep.name, ep.value, str(e),
                    exc_info=True
                )

        self._loaded_groups.add(group)


registry = PluginRegistry()
"Глобальный экземпляр реестра"


def register_plugin(plugin: Any) -> None:
    """Публичная функция для явной регистрации плагина.

    Args:
        plugin: Объект или класс регистрируемого плагина.
    """
    registry.register(plugin)
