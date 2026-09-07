"""
Миксин для трассировки параметров конфигурации.
"""

from __future__ import annotations

import copy
import os
import threading
from typing import Any

from chutils.typing import JSONDict


class _ConfigTracingMixin:
    """Миксин для отслеживания истории изменений значений параметров конфигурации."""

    _lock: threading.RLock
    _tracing_enabled: bool
    _trace_data: dict[str, dict[str, list[dict[str, Any]]]]

    def _init_tracing(self) -> None:
        """Инициализирует состояние трассировки."""
        self._tracing_enabled = False
        self._trace_data = {}

    @property
    def tracing_enabled(self) -> bool:
        """Флаг включения трассировки."""
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
            self._trace_data[s_key][k_key].append({"source": source, "value": value})

    def get_trace(self) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """Возвращает собранные данные трассировки.

        Returns:
            Словарь со всеми данными трассировки параметров.
        """
        with self._lock:
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
                    self.record_trace("default", section, keys, source)

    def trace_env_vars(self) -> None:
        """Сканирует переменные окружения и записывает их в трассировку."""
        with self._lock:
            if not self._tracing_enabled:
                return

            # chutils: ignore[ChutilsIntegrationRule]
            disable_env_override = os.getenv("CH_DISABLE_ENV_OVERRIDE", "").lower() in (
                "true",
                "1",
                "yes",
                "y",
            )
            if disable_env_override:
                return

            # chutils: ignore[ChutilsIntegrationRule]
            for env_key, env_value in os.environ.items():
                if env_key.startswith("CH_") and env_key not in (
                        "CH_ENV",
                        "CH_DISABLE_ENV_OVERRIDE",
                        "CH_DISABLE_KEYRING_WARNING",
                ):
                    parts = env_key[3:].split("_", 1)
                    if len(parts) == 2:
                        section, key = parts
                        self.record_trace(
                            section.lower(), key.lower(), env_value, "env"
                        )

            # Специфический ключ для secrets
            # chutils: ignore[ChutilsIntegrationRule]
            secrets_env = os.getenv("CH_DISABLE_KEYRING_WARNING")
            if secrets_env is not None:
                self.record_trace("secrets", "disable_keyring", secrets_env, "env")
