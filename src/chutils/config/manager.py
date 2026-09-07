"""
Менеджер состояния конфигурации.
Инкапсулирует глобальные переменные и логику управления состоянием конфигурации.
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
import threading
import time
from collections.abc import Callable
from typing import Any, cast

from typing_extensions import Self

from chutils.typing import JSONDict

from .paths import _ConfigPathsMixin
from .tracing import _ConfigTracingMixin

# Настраиваем локальный логгер

logger = logging.getLogger(__name__)  # chutils: ignore[ChutilsIntegrationRule]


class _ConfigManager(_ConfigPathsMixin, _ConfigTracingMixin):
    """
    Менеджер состояния конфигурации (Синглтон).
    Управляет путями к файлам, кэшированием, провайдерами и трассировкой.
    """

    _instance: _ConfigManager | None = None

    # Объявление типов для статического анализатора (strict mode)
    _lock: threading.RLock
    _loading_lock: threading.RLock
    _file_lock: threading.RLock
    _config_object: JSONDict | None
    _features_object: JSONDict | None
    _config_loaded: bool
    _features_loaded: bool
    _observer: Any | None
    _callbacks: list[Callable[[], Any]]
    _last_reload_time: float
    _last_internal_save_time: float
    _remote_provider: Any | None
    _sse_client: Any | None
    _webhook_server: Any | None
    _custom_providers_registry: Any | None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = threading.RLock()
            cls._instance._loading_lock = threading.RLock()
            cls._instance._file_lock = threading.RLock()
            cls._instance._reset()
        return cast(Self, cls._instance)

    def _reset(self) -> None:
        """Сбрасывает состояние менеджера (полезно для тестов)."""
        with self._lock:
            self._init_paths()
            self._init_tracing()
            self._config_object = None
            self._features_object = None
            self._config_loaded = False
            self._features_loaded = False
            self._observer = None
            self._callbacks = []
            self._last_reload_time = 0.0
            self._last_internal_save_time = 0.0
            if hasattr(self, "_remote_provider") and self._remote_provider is not None:
                if hasattr(self._remote_provider, "stop_polling"):
                    self._remote_provider.stop_polling()
                self._remote_provider = None
            else:
                self._remote_provider = None

            if hasattr(self, "_sse_client") and self._sse_client is not None:
                if hasattr(self._sse_client, "stop"):
                    self._sse_client.stop()
                self._sse_client = None
            else:
                self._sse_client = None

            if hasattr(self, "_webhook_server") and self._webhook_server is not None:
                if hasattr(self._webhook_server, "stop"):
                    self._webhook_server.stop()
                self._webhook_server = None
            else:
                self._webhook_server = None

            # Сбрасываем реестр кастомных провайдеров (если уже инициализирован)
            if (
                hasattr(self, "_custom_providers_registry")
                and self._custom_providers_registry is not None
            ):
                self._custom_providers_registry.reset()
            else:
                self._custom_providers_registry = None

    def register_provider(self, provider: Any, priority: int = 100) -> None:
        """Регистрирует кастомный провайдер конфигурации.

        Args:
            provider: Экземпляр, реализующий BaseConfigProvider.
            priority: Числовой приоритет (меньше → выше). По умолчанию: 100.
        """
        from .custom_providers import get_registry

        registry = get_registry()
        registry.register(provider, priority)

    def reset_providers(self) -> None:
        """Очищает реестр кастомных провайдеров.

        Используется в тестах для сброса состояния между тест-кейсами.
        """
        from .custom_providers import get_registry

        get_registry().reset()

    @property
    def remote_provider(self) -> Any | None:
        with self._lock:
            return self._remote_provider

    @remote_provider.setter
    def remote_provider(self, value: Any | None) -> None:
        with self._lock:
            self._remote_provider = value

    @property
    def sse_client(self) -> Any | None:
        with self._lock:
            return self._sse_client

    @sse_client.setter
    def sse_client(self, value: Any | None) -> None:
        with self._lock:
            self._sse_client = value

    @property
    def webhook_server(self) -> Any | None:
        with self._lock:
            return self._webhook_server

    @webhook_server.setter
    def webhook_server(self, value: Any | None) -> None:
        with self._lock:
            self._webhook_server = value

    def start_webhook_server(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        path: str = "/webhook/config-reload",
        secret_token: str | None = None,
        hmac_secret: str | None = None,
    ) -> Any:
        """
        Запускает встроенный Webhook-сервер для мгновенного обновления конфигурации.

        Args:
            host: Хост прослушивания (по умолчанию 0.0.0.0).
            port: Порт прослушивания (0 — случайный порт).
            path: Путь эндпоинта (по умолчанию /webhook/config-reload).
            secret_token: Опциональный токен авторизации.
            hmac_secret: Опциональный секретный ключ HMAC-SHA256.

        Returns:
            Экземпляр WebhookConfigServer.
        """
        with self._lock:
            if self._webhook_server:
                self._webhook_server.stop()

            from .webhook_server import WebhookConfigServer

            server = WebhookConfigServer(
                host=host,
                port=port,
                path=path,
                secret_token=secret_token,
                hmac_secret=hmac_secret,
                on_reload=self.trigger_reload,
            )
            self._webhook_server = server
            server.start()
            return server

    def stop_webhook_server(self) -> None:
        """Останавливает запущенный встроенный Webhook-сервер."""
        with self._lock:
            if self._webhook_server:
                self._webhook_server.stop()
                self._webhook_server = None

    def trigger_reload(self) -> None:
        """
        Принудительно перезагружает конфигурацию.
        Сбрасывает кэш и оповещает все зарегистрированные колбэки.
        """
        with self._lock:
            self.clear_cache()
            callbacks = list(self._callbacks)

        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                logger.error("Ошибка при вызове колбэка обновления конфигурации: %s", e)

    @property
    def config_object(self) -> JSONDict | None:
        with self._lock:
            return self._config_object

    @config_object.setter
    def config_object(self, value: JSONDict | None) -> None:
        with self._lock:
            self._config_object = value

    @property
    def config_loaded(self) -> bool:
        with self._lock:
            return self._config_loaded

    @config_loaded.setter
    def config_loaded(self, value: bool) -> None:
        with self._lock:
            self._config_loaded = value

    @property
    def observer(self) -> Any | None:
        with self._lock:
            return self._observer

    @observer.setter
    def observer(self, value: Any | None) -> None:
        with self._lock:
            self._observer = value

    @property
    def last_reload_time(self) -> float:
        with self._lock:
            return self._last_reload_time

    @last_reload_time.setter
    def last_reload_time(self, value: float) -> None:
        with self._lock:
            self._last_reload_time = value

    @property
    def features_object(self) -> JSONDict | None:
        with self._lock:
            return self._features_object

    @features_object.setter
    def features_object(self, value: JSONDict | None) -> None:
        with self._lock:
            self._features_object = value

    @property
    def features_loaded(self) -> bool:
        with self._lock:
            return self._features_loaded

    @features_loaded.setter
    def features_loaded(self, value: bool) -> None:
        with self._lock:
            self._features_loaded = value

    def set_config(self, config_data: JSONDict) -> None:
        """Устанавливает новый объект конфигурации в кэш атомарно.

        Args:
            config_data: Словарь данных конфигурации.
        """
        with self._lock:
            self._config_object = config_data
            self._config_loaded = True

    def set_features(self, features_data: JSONDict) -> None:
        """Устанавливает новый объект фича-флагов в кэш атомарно.

        Args:
            features_data: Словарь фича-флагов.
        """
        with self._lock:
            self._features_object = features_data
            self._features_loaded = True

    def check_internal_save(self, threshold: float = 0.5) -> bool:
        """Проверяет, было ли недавнее внутреннее сохранение, и сбрасывает флаг.

        Args:
            threshold: Порог времени в секундах.

        Returns:
            True если недавнее сохранение было выполнено.
        """
        with self._lock:
            current_time = time.monotonic()
            if current_time - self._last_internal_save_time < threshold:
                self._last_internal_save_time = 0.0
                return True
            return False

    def mark_internal_save(self) -> None:
        """Устанавливает время последнего внутреннего сохранения."""
        with self._lock:
            self._last_internal_save_time = time.monotonic()

    def get_callbacks(self) -> list[Callable[[], Any]]:
        """Возвращает копию списка коллбэков.

        Returns:
            Список зарегистрированных callback-функций.
        """
        with self._lock:
            return list(self._callbacks)

    def add_callback(self, callback: Callable[[], Any]) -> bool:
        """Добавляет коллбэк, если его еще нет.

        Args:
            callback: Функция обратного вызова.

        Returns:
            True если коллбэк был добавлен.
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
                return True
            return False

    def clear_cache(self) -> None:
        """Сбрасывает кэш загруженной конфигурации и фича-флагов атомарно."""
        with self._lock:
            self._config_object = None
            self._config_loaded = False
            self.clear_features_cache()

    def clear_features_cache(self) -> None:
        """Сбрасывает кэш фича-флагов атомарно."""
        with self._lock:
            self._features_object = None
            self._features_loaded = False

    def load_config_safe(self, load_func: Callable[[], JSONDict]) -> JSONDict:
        """Потокобезопасно загружает конфигурацию, если она еще не загружена.

        Использует loading_lock для предотвращения конкурентной загрузки из файлов.

        Args:
            load_func: Функция загрузки словаря конфигурации.

        Returns:
            Словарь конфигурации.
        """
        with self._lock:
            if self._config_loaded and self._config_object is not None:
                return self._config_object

        with self._loading_lock:
            with self._lock:
                if self._config_loaded and self._config_object is not None:
                    return self._config_object

            data = load_func()
            self.set_config(data)
            return data

    def load_features_safe(self, load_func: Callable[[], JSONDict]) -> JSONDict:
        """Потокобезопасно загружает фича-флаги, если они еще не загружены.

        Использует loading_lock для предотвращения конкурентной загрузки из файлов.

        Args:
            load_func: Функция загрузки словаря фича-флагов.

        Returns:
            Словарь фича-флагов.
        """
        with self._lock:
            if self._features_loaded and self._features_object is not None:
                return self._features_object

        with self._loading_lock:
            with self._lock:
                if self._features_loaded and self._features_object is not None:
                    return self._features_object

            data = load_func()
            self.set_features(data)
            return data

    def acquire_file_lock(self) -> None:
        """Захватывает блокировку для работы с файлами конфигурации."""
        self._file_lock.acquire()

    def release_file_lock(self) -> None:
        """Освобождает блокировку файлов."""
        self._file_lock.release()


_cm = _ConfigManager()
"""Глобальный экземпляр менеджера."""
