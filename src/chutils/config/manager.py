"""
Менеджер состояния конфигурации.
Инкапсулирует глобальные переменные и логику инициализации путей.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

# Настраиваем локальный логгер
logger = logging.getLogger(__name__)


class _ConfigManager:
    """
    Менеджер состояния конфигурации (Синглтон).
    Управляет путями к файлам и кэшированием загруженного объекта конфигурации.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(_ConfigManager, cls).__new__(cls)
            cls._instance._reset()
        return cls._instance

    def _reset(self):
        """Сбрасывает состояние менеджера (полезно для тестов)."""
        self.base_dir: Optional[str] = None
        self.config_file_path: Optional[str] = None
        self.paths_initialized = False
        self.config_object: Optional[Dict] = None
        self.config_loaded = False

    def initialize_paths(self, find_root_func):
        """
        Инициализирует пути к корню проекта и основному файлу конфигурации.
        """
        if self.paths_initialized:
            return

        # В некоторых окружениях тестов Path.cwd() может вызвать ошибку, если директория удалена
        try:
            current_dir = Path.cwd()
        except OSError:
            current_dir = Path('.')

        markers = [
            'config.yml', 'config.yaml', 'config.ini', 'config.json',
            'config.local.yml', 'config.local.yaml', 'config.local.ini', 'config.local.json',
            'pyproject.toml'
        ]
        project_root = find_root_func(current_dir, markers)

        if project_root:
            self.base_dir = str(project_root)
            # Находим, какой именно конфигурационный файл был найден
            for marker in markers:
                if (project_root / marker).is_file() and marker.startswith('config'):
                    self.config_file_path = str(project_root / marker)
                    break
            logger.debug("Корень проекта автоматически определен: %s", self.base_dir)
        else:
            logger.warning("Не удалось автоматически найти корень проекта.")

        self.paths_initialized = True

    def get_config_paths(self, cfg_file: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Возвращает пути к основному и локальному файлам конфигурации.
        """
        main_config_path: Optional[str] = None
        local_config_path: Optional[str] = None

        if cfg_file:
            main_config_path = cfg_file
        else:
            # Пути должны быть инициализированы перед использованием
            main_config_path = self.config_file_path

        if main_config_path:
            main_path_obj = Path(main_config_path)
            file_ext = main_path_obj.suffix.lower()
            local_file_name = f"{main_path_obj.stem}.local{file_ext}"
            potential_local_path = main_path_obj.parent / local_file_name
            if potential_local_path.exists():
                local_config_path = str(potential_local_path)
                logger.debug("Найден локальный файл конфигурации: %s", local_config_path)

        return main_config_path, local_config_path


# Глобальный экземпляр менеджера
_cm = _ConfigManager()
