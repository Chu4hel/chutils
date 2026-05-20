"""
Менеджер состояния конфигурации.
Инкапсулирует глобальные переменные и логику инициализации путей.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, List

# Настраиваем локальный логгер
logger = logging.getLogger(__name__)


class _ConfigManager:
    """
    Менеджер состояния конфигурации (Синглтон).
    Управляет путями к файлам и кэшированием загруженного объекта конфигурации.
    """
    _instance = None

    # Список маркеров, по которым ищется корень проекта и конфигурационные файлы.
    # Порядок в списке определяет приоритет при поиске.
    CONFIG_MARKERS = [
        'config.yml', 'config.yaml', 'config.ini', 'config.json',
        'config.local.yml', 'config.local.yaml', 'config.local.ini', 'config.local.json',
        'pyproject.toml'
    ]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(_ConfigManager, cls).__new__(cls)
            cls._instance._lock = threading.RLock()
            cls._instance._loading_lock = threading.RLock()
            cls._instance._file_lock = threading.RLock()
            cls._instance._reset()
        return cls._instance

    def _reset(self):
        """Сбрасывает состояние менеджера (полезно для тестов)."""
        with self._lock:
            self._base_dir: Optional[str] = None
            self._config_file_path: Optional[str] = None
            self._features_file_path: Optional[str] = None
            self._paths_initialized = False
            self._config_object: Optional[Dict] = None
            self._features_object: Optional[Dict] = None
            self._config_loaded = False
            self._features_loaded = False
            self._observer: Optional[Any] = None
            self._callbacks: List = []
            self._last_reload_time: float = 0.0
            self._last_internal_save_time: float = 0.0

    @property
    def base_dir(self) -> Optional[str]:
        with self._lock:
            return self._base_dir

    @base_dir.setter
    def base_dir(self, value: Optional[str]):
        with self._lock:
            self._base_dir = value

    @property
    def config_file_path(self) -> Optional[str]:
        with self._lock:
            return self._config_file_path

    @config_file_path.setter
    def config_file_path(self, value: Optional[str]):
        with self._lock:
            self._config_file_path = value

    @property
    def paths_initialized(self) -> bool:
        with self._lock:
            return self._paths_initialized

    @paths_initialized.setter
    def paths_initialized(self, value: bool):
        with self._lock:
            self._paths_initialized = value

    @property
    def config_object(self) -> Optional[Dict]:
        with self._lock:
            return self._config_object

    @config_object.setter
    def config_object(self, value: Optional[Dict]):
        with self._lock:
            self._config_object = value

    @property
    def config_loaded(self) -> bool:
        with self._lock:
            return self._config_loaded

    @config_loaded.setter
    def config_loaded(self, value: bool):
        with self._lock:
            self._config_loaded = value

    @property
    def observer(self) -> Optional[Any]:
        with self._lock:
            return self._observer

    @observer.setter
    def observer(self, value: Optional[Any]):
        with self._lock:
            self._observer = value

    @property
    def last_reload_time(self) -> float:
        with self._lock:
            return self._last_reload_time

    @last_reload_time.setter
    def last_reload_time(self, value: float):
        with self._lock:
            self._last_reload_time = value

    @property
    def features_file_path(self) -> Optional[str]:
        with self._lock:
            return self._features_file_path

    @features_file_path.setter
    def features_file_path(self, value: Optional[str]):
        with self._lock:
            self._features_file_path = value

    @property
    def features_object(self) -> Optional[Dict]:
        with self._lock:
            return self._features_object

    @features_object.setter
    def features_object(self, value: Optional[Dict]):
        with self._lock:
            self._features_object = value

    @property
    def features_loaded(self) -> bool:
        with self._lock:
            return self._features_loaded

    @features_loaded.setter
    def features_loaded(self, value: bool):
        with self._lock:
            self._features_loaded = value

    def set_config(self, config_data: Dict[str, Any]):
        """Устанавливает новый объект конфигурации в кэш атомарно."""
        with self._lock:
            self._config_object = config_data
            self._config_loaded = True

    def set_features(self, features_data: Dict[str, Any]):
        """Устанавливает новый объект фича-флагов в кэш атомарно."""
        with self._lock:
            self._features_object = features_data
            self._features_loaded = True

    def check_internal_save(self, threshold: float = 0.5) -> bool:
        """Проверяет, было ли недавнее внутреннее сохранение, и сбрасывает флаг."""
        with self._lock:
            current_time = time.monotonic()
            if current_time - self._last_internal_save_time < threshold:
                self._last_internal_save_time = 0.0
                return True
            return False

    def mark_internal_save(self):
        """Устанавливает время последнего внутреннего сохранения."""
        with self._lock:
            self._last_internal_save_time = time.monotonic()

    def get_callbacks(self) -> List:
        """Возвращает копию списка коллбэков."""
        with self._lock:
            return list(self._callbacks)

    def add_callback(self, callback: Any):
        """Добавляет коллбэк, если его еще нет."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
                return True
            return False

    def initialize_paths(self, find_root_func):
        """
        Инициализирует пути к корню проекта и основному файлу конфигурации.
        Использует loading_lock для предотвращения конкурентной инициализации.
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

    def get_config_paths(self, cfg_file: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Возвращает пути к основному, специфичному для окружения и локальному файлам конфигурации.
        """
        with self._lock:
            main_config_path: Optional[str] = None
            env_config_path: Optional[str] = None
            local_config_path: Optional[str] = None

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
                ch_env = os.getenv("CH_ENV", "development")
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

    def clear_cache(self):
        """Сбрасывает кэш загруженной конфигурации и фича-флагов атомарно."""
        with self._lock:
            self._config_object = None
            self._config_loaded = False
            self.clear_features_cache()

    def clear_features_cache(self):
        """Сбрасывает кэш фича-флагов атомарно."""
        with self._lock:
            self._features_object = None
            self._features_loaded = False

    def load_config_safe(self, load_func: Any) -> Dict[str, Any]:
        """
        Потокобезопасно загружает конфигурацию, если она еще не загружена.
        Использует loading_lock для предотвращения конкурентной загрузки из файлов.
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

    def load_features_safe(self, load_func: Any) -> Dict[str, Any]:
        """
        Потокобезопасно загружает фича-флаги, если они еще не загружены.
        Использует loading_lock для предотвращения конкурентной загрузки из файлов.
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

    def acquire_file_lock(self):
        """Захватывает блокировку для работы с файлами конфигурации."""
        self._file_lock.acquire()

    def release_file_lock(self):
        """Освобождает блокировку файлов."""
        self._file_lock.release()


# Глобальный экземпляр менеджера
_cm = _ConfigManager()
