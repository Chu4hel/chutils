"""Модели данных конфигурации прокси-серверов.

Реэкспортирует базовые модели ProxyConfig и ProxyHealthResult из ядра chutils.http.models.
"""

from __future__ import annotations

from chutils.http.models import ProxyConfig, ProxyHealthResult

__all__ = ["ProxyConfig", "ProxyHealthResult"]
