"""
Миксин для управления путями конфигурации и поиска корня проекта.
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger(__name__)  # chutils: ignore[ChutilsIntegrationRule]


class _ConfigPathsMixin:
    """Миксин для управления путями к файлам конфигурации."""

    _lock: threading.RLock
    _loading_lock: threading.RLock
    _base_dir: str | None
    _config_file_path: str | None
    _features_file_path: str | None
    _paths_initialized: bool

    # Список основных маркеров, по которым ищется корень проекта.
    CONFIG_MARKERS: ClassVar[list[str]] = [
        "config.yml",
        "config.yaml",
        "config.ini",
        "config.json",
        "config.local.yml",
        "config.local.yaml",
        "config.local.ini",
        "config.local.json",
        "pyproject.toml",
        ".git",
    ]

    # Вторичные (fallback) маркеры корня проекта (AI-манифесты и конфигурации редакторов).
    FALLBACK_MARKERS: ClassVar[list[str]] = [
        "antigravity.md",
        "gemini.md",
        "GEMINI.md",
        "agents.md",
        "AGENTS.md",
        ".cursorrules",
        ".windsurfrules",
    ]

    def _init_paths(self) -> None:
        """Инициализирует состояние путей."""
        self._base_dir = None
        self._config_file_path = None
        self._features_file_path = None
        self._paths_initialized = False

    @property
    def base_dir(self) -> str | None:
        """Базовая директория (корень проекта)."""
        with self._lock:
            return self._base_dir

    @base_dir.setter
    def base_dir(self, value: str | None) -> None:
        with self._lock:
            self._base_dir = value

    @property
    def config_file_path(self) -> str | None:
        """Путь к основному файлу конфигурации."""
        with self._lock:
            return self._config_file_path

    @config_file_path.setter
    def config_file_path(self, value: str | None) -> None:
        with self._lock:
            self._config_file_path = value

    @property
    def features_file_path(self) -> str | None:
        """Путь к файлу фича-флагов."""
        with self._lock:
            return self._features_file_path

    @features_file_path.setter
    def features_file_path(self, value: str | None) -> None:
        with self._lock:
            self._features_file_path = value

    @property
    def paths_initialized(self) -> bool:
        """Флаг инициализации путей."""
        with self._lock:
            return self._paths_initialized

    @paths_initialized.setter
    def paths_initialized(self, value: bool) -> None:
        with self._lock:
            self._paths_initialized = value

    def initialize_paths(
            self, find_root_func: Callable[[Path, list[str]], Path | None]
    ) -> None:
        """Инициализирует пути к корню проекта и основному файлу конфигурации.

        Использует loading_lock для предотвращения конкурентной инициализации.

        Args:
            find_root_func: Функция поиска корня проекта.
        """
        if self.paths_initialized:
            return

        with self._loading_lock:
            if self.paths_initialized:
                return

            try:
                current_dir = Path.cwd()
            except OSError:
                current_dir = Path(".")

            project_root = find_root_func(current_dir, self.CONFIG_MARKERS)
            if not project_root:
                project_root = find_root_func(current_dir, self.FALLBACK_MARKERS)

            if project_root:
                self.base_dir = str(project_root)
                for marker in self.CONFIG_MARKERS:
                    if (project_root / marker).is_file() and marker.startswith(
                            "config"
                    ):
                        self.config_file_path = str(project_root / marker)
                        break

                for marker in ["features.yml", "features.yaml"]:
                    if (project_root / marker).is_file():
                        self.features_file_path = str(project_root / marker)
                        break

                logger.debug(
                    "Корень проекта автоматически определен: %s", self.base_dir
                )
            else:
                logger.warning("Не удалось автоматически найти корень проекта.")

            self.paths_initialized = True

    def get_config_paths(
            self, cfg_file: str | None = None
    ) -> tuple[str | None, str | None]:
        """Возвращает пути к основному и локальному файлам конфигурации (Legacy API).

        Для получения всех путей (включая env) используйте get_all_config_paths().

        Args:
            cfg_file: Явно указанный путь к основному файлу конфигурации.

        Returns:
            Кортеж путей (основной, локальный).
        """
        main, _, local = self.get_all_config_paths(cfg_file)
        return main, local

    def get_all_config_paths(
            self, cfg_file: str | None = None
    ) -> tuple[str | None, str | None, str | None]:
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
                main_config_path = self._config_file_path

            if main_config_path:
                main_path_obj = Path(main_config_path)
                file_ext = main_path_obj.suffix.lower()

                # chutils: ignore[ChutilsIntegrationRule]
                ch_env = os.getenv("CH_ENV", "development")
                env_file_name = f"{main_path_obj.stem}.{ch_env}{file_ext}"
                potential_env_path = main_path_obj.parent / env_file_name
                if potential_env_path.exists():
                    env_config_path = str(potential_env_path)
                    logger.debug(
                        "Найден конфигурационный файл окружения (%s): %s",
                        ch_env,
                        env_config_path,
                    )

                local_file_name = f"{main_path_obj.stem}.local{file_ext}"
                potential_local_path = main_path_obj.parent / local_file_name
                if potential_local_path.exists():
                    local_config_path = str(potential_local_path)
                    logger.debug(
                        "Найден локальный файл конфигурации: %s", local_config_path
                    )

            return main_config_path, env_config_path, local_config_path
