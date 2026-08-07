"""
Менеджер состояния конфигурации.
Инкапсулирует глобальные переменные и логику инициализации путей.
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from chutils.typing import JSONDict

# Настраиваем локальный логгер

logger = logging.getLogger(__name__)  # chutils: ignore[ChutilsIntegrationRule]


class _ConfigManager:
    """
    Менеджер состояния конфигурации (Синглтон).
    Управляет путями к файлам и кэшированием загруженного объекта конфигурации.
    """
    _instance: _ConfigManager | None = None

    # Объявление типов для статического анализатора (strict mode)
    _lock: threading.RLock
    _loading_lock: threading.RLock
    _file_lock: threading.RLock
    _base_dir: str | None
    _config_file_path: str | None
    _features_file_path: str | None
    _paths_initialized: bool
    _config_object: JSONDict | None
    _features_object: JSONDict | None
    _config_loaded: bool
    _features_loaded: bool
    _observer: Any | None
    _callbacks: list[Callable[[], Any]]
    _last_reload_time: float
    _last_internal_save_time: float
    _tracing_enabled: bool
    _trace_data: dict[str, dict[str, list[dict[str, Any]]]]
    _remote_provider: Any | None
    _sse_client: Any | None
    _webhook_server: Any | None
    _custom_providers_registry: Any | None

    # Список маркеров, по которым ищется корень проекта и конфигурационные файлы.
    # Порядок в списке определяет приоритет при поиске.
    CONFIG_MARKERS: list[str] = [
        'config.yml', 'config.yaml', 'config.ini', 'config.json',
        'config.local.yml', 'config.local.yaml', 'config.local.ini', 'config.local.json',
        'pyproject.toml'
    ]

    def __new__(cls) -> _ConfigManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = threading.RLock()
            cls._instance._loading_lock = threading.RLock()
            cls._instance._file_lock = threading.RLock()
            cls._instance._reset()
        return cls._instance

    def _reset(self) -> None:
        """Сбрасывает состояние менеджера (полезно для тестов)."""
        with self._lock:
            self._base_dir = None
            self._config_file_path = None
            self._features_file_path = None
            self._paths_initialized = False
            self._config_object = None
            self._features_object = None
            self._config_loaded = False
            self._features_loaded = False
            self._observer = None
            self._callbacks = []
            self._last_reload_time = 0.0
            self._last_internal_save_time = 0.0
            self._tracing_enabled = False
            self._trace_data = {}
            if hasattr(self, '_remote_provider') and self._remote_provider is not None:
                if hasattr(self._remote_provider, 'stop_polling'):
                    self._remote_provider.stop_polling()
                self._remote_provider = None
            else:
                self._remote_provider = None

            if hasattr(self, '_sse_client') and self._sse_client is not None:
                if hasattr(self._sse_client, 'stop'):
                    self._sse_client.stop()
                self._sse_client = None
            else:
                self._sse_client = None

            if hasattr(self, '_webhook_server') and self._webhook_server is not None:
                if hasattr(self._webhook_server, 'stop'):
                    self._webhook_server.stop()
                self._webhook_server = None
            else:
                self._webhook_server = None

            # Сбрасываем реестр кастомных провайдеров (если уже инициализирован)
            if hasattr(self, '_custom_providers_registry') and self._custom_providers_registry is not None:
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
    def tracing_enabled(self) -> bool:
        with self._lock:
            return self._tracing_enabled

    @tracing_enabled.setter
    def tracing_enabled(self, value: bool) -> None:
        with self._lock:
            self._tracing_enabled = value
            if not value:
                self._trace_data = {}

    def record_trace(self, section: str, key: str, value: Any, source: str) -> None:
        """Записывает историю изменения значения ключа.

        Args:
            section: Имя секции конфигурации.
            key: Ключ внутри секции.
            value: Устанавливаемое значение.
            source: Источник изменения.
        """
        with self._lock:
            if not self._tracing_enabled:
                return

            s_key = section.lower()
            k_key = key.lower()

            if s_key not in self._trace_data:
                self._trace_data[s_key] = {}
            if k_key not in self._trace_data[s_key]:
                self._trace_data[s_key][k_key] = []

            # Добавляем в историю
            self._trace_data[s_key][k_key].append({
                "source": source,
                "value": value
            })

    def get_trace(self) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """Возвращает собранные данные трассировки.

        Returns:
            Словарь со всеми данными трассировки параметров.
        """
        with self._lock:
            import copy
            return copy.deepcopy(self._trace_data)

    def record_trace_dict(self, data: JSONDict, source: str) -> None:
        """Записывает все значения из словаря в трассировку.

        Args:
            data: Данные конфигурации в формате словаря.
            source: Имя источника конфигурации.
        """
        with self._lock:
            if not self._tracing_enabled:
                return

            for section, keys in data.items():
                if isinstance(keys, dict):
                    for key, value in keys.items():
                        self.record_trace(section, key, value, source)
                else:
                    # Корневые ключи (если есть) рассматриваем как принадлежащие секции 'default'
                    # или игнорируем, если архитектура предполагает только секции.
                    # В chutils основные конфиги - это секции.
                    self.record_trace("default", section, keys, source)

    def trace_env_vars(self) -> None:
        """Сканирует переменные окружения и записывает их в трассировку."""
        import os
        with self._lock:
            if not self._tracing_enabled:
                return

            disable_env_override = os.getenv("CH_DISABLE_ENV_OVERRIDE", "").lower() in ("true", "1", "yes", "y")  # chutils: ignore[ChutilsIntegrationRule]
            if disable_env_override:
                return

            for env_key, env_value in os.environ.items():  # chutils: ignore[ChutilsIntegrationRule]
                if env_key.startswith("CH_") and env_key not in ("CH_ENV", "CH_DISABLE_ENV_OVERRIDE",
                                                                 "CH_DISABLE_KEYRING_WARNING"):
                    # Шаблон: CH_[SECTION]_[KEY]
                    # Пытаемся разбить по первому нижнему подчеркиванию после CH_
                    # Это упрощенный парсинг, так как секция или ключ сами могут содержать _
                    # Но согласно спецификации, мы берем CH_SECTION_KEY.
                    parts = env_key[3:].split('_', 1)
                    if len(parts) == 2:
                        section, key = parts
                        # Мы сохраняем в нижнем регистре для консистентности с ключами из файлов
                        self.record_trace(section.lower(), key.lower(), env_value, "env")

            # Специфический ключ для secrets
            secrets_env = os.getenv("CH_DISABLE_KEYRING_WARNING")  # chutils: ignore[ChutilsIntegrationRule]
            if secrets_env is not None:
                self.record_trace("secrets", "disable_keyring", secrets_env, "env")

    @property
    def base_dir(self) -> str | None:
        with self._lock:
            return self._base_dir

    @base_dir.setter
    def base_dir(self, value: str | None) -> None:
        with self._lock:
            self._base_dir = value

    @property
    def config_file_path(self) -> str | None:
        with self._lock:
            return self._config_file_path

    @config_file_path.setter
    def config_file_path(self, value: str | None) -> None:
        with self._lock:
            self._config_file_path = value

    @property
    def paths_initialized(self) -> bool:
        with self._lock:
            return self._paths_initialized

    @paths_initialized.setter
    def paths_initialized(self, value: bool) -> None:
        with self._lock:
            self._paths_initialized = value

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
    def features_file_path(self) -> str | None:
        with self._lock:
            return self._features_file_path

    @features_file_path.setter
    def features_file_path(self, value: str | None) -> None:
        with self._lock:
            self._features_file_path = value

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

    def initialize_paths(self, find_root_func: Callable[[Path, list[str]], Path | None]) -> None:
        """Инициализирует пути к корню проекта и основному файлу конфигурации.

        Использует loading_lock для предотвращения конкурентной инициализации.

        Args:
            find_root_func: Функция поиска корня проекта.
        """
        if self.paths_initialized:
            return

        with self._loading_lock:
            # Двойная проверка под блокировкой
            if self.paths_initialized:
                return

            # В некоторых окружениях тестов Path.cwd() может вызвать ошибку, если директория удалена
            try:
                current_dir = Path.cwd()
            except OSError:
                current_dir = Path('.')

            project_root = find_root_func(current_dir, self.CONFIG_MARKERS)

            if project_root:
                self.base_dir = str(project_root)
                # Находим, какой именно конфигурационный файл был найден
                for marker in self.CONFIG_MARKERS:
                    if (project_root / marker).is_file() and marker.startswith('config'):
                        self.config_file_path = str(project_root / marker)
                        break

                # Находим features.yml (фича-флаги)
                for marker in ['features.yml', 'features.yaml']:
                    if (project_root / marker).is_file():
                        self.features_file_path = str(project_root / marker)
                        break

                logger.debug("Корень проекта автоматически определен: %s", self.base_dir)
            else:
                logger.warning("Не удалось автоматически найти корень проекта.")

            self.paths_initialized = True

    def get_config_paths(self, cfg_file: str | None = None) -> tuple[str | None, str | None]:
        """Возвращает пути к основному и локальному файлам конфигурации (Legacy API).

        Для получения всех путей (включая env) используйте get_all_config_paths().

        Args:
            cfg_file: Явно указанный путь к основному файлу конфигурации.

        Returns:
            Кортеж путей (основной, локальный).
        """
        main, _, local = self.get_all_config_paths(cfg_file)
        return main, local

    def get_all_config_paths(self, cfg_file: str | None = None) -> tuple[
        str | None, str | None, str | None]:
        """Возвращает пути к основному, специфичному для окружения и локальному файлам конфигурации.

        Args:
            cfg_file: Явно указанный путь к файлу конфигурации.

        Returns:
            Кортеж (main_path, env_path, local_path).
        """
        with self._lock:
            main_config_path: str | None = None
            env_config_path: str | None = None
            local_config_path: str | None = None

            if cfg_file:
                main_config_path = cfg_file
            else:
                # Пути должны быть инициализированы перед использованием
                main_config_path = self._config_file_path

            if main_config_path:
                main_path_obj = Path(main_config_path)
                file_ext = main_path_obj.suffix.lower()

                # 1. Специфичный для окружения (например, config.production.yml)
                import os
                ch_env = os.getenv("CH_ENV", "development")  # chutils: ignore[ChutilsIntegrationRule]
                env_file_name = f"{main_path_obj.stem}.{ch_env}{file_ext}"
                potential_env_path = main_path_obj.parent / env_file_name
                if potential_env_path.exists():
                    env_config_path = str(potential_env_path)
                    logger.debug("Найден конфигурационный файл окружения (%s): %s", ch_env, env_config_path)

                # 2. Локальное (config.local.yml)
                local_file_name = f"{main_path_obj.stem}.local{file_ext}"
                potential_local_path = main_path_obj.parent / local_file_name
                if potential_local_path.exists():
                    local_config_path = str(potential_local_path)
                    logger.debug("Найден локальный файл конфигурации: %s", local_config_path)

            return main_config_path, env_config_path, local_config_path

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
        # Атомарная проверка состояния кэша под основной блокировкой
        with self._lock:
            if self._config_loaded and self._config_object is not None:
                return self._config_object

        with self._loading_lock:
            # Двойная проверка под блокировкой
            with self._lock:
                if self._config_loaded and self._config_object is not None:
                    return self._config_object

            # Выполняем загрузку (может быть медленной I/O операцией)
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
        # Атомарная проверка состояния кэша под основной блокировкой
        with self._lock:
            if self._features_loaded and self._features_object is not None:
                return self._features_object

        with self._loading_lock:
            # Двойная проверка под блокировкой
            with self._lock:
                if self._features_loaded and self._features_object is not None:
                    return self._features_object

            # Выполняем загрузку
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
