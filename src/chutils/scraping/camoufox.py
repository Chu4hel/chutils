"""Интеграция с антидетект-браузером Camoufox (Playwright Firefox wrapper)."""

from __future__ import annotations

import importlib.util
from typing import Any

from chutils.exceptions import OptionalDependencyError

CAMOUFOX_AVAILABLE = importlib.util.find_spec("camoufox") is not None


def get_async_camoufox_class() -> Any:
    """Возвращает класс AsyncCamoufox из библиотеки camoufox.

    Returns:
        Класс AsyncCamoufox.

    Raises:
        OptionalDependencyError: Если библиотека camoufox не установлена.
    """
    if not CAMOUFOX_AVAILABLE:
        raise OptionalDependencyError(
            "Для использования Camoufox требуется библиотека 'camoufox'.\n"
            "Установите её: pip install chutils[camoufox] или pip install camoufox",
            dependency="camoufox",
            hint="Выполните pip install camoufox",
        )
    from camoufox.async_api import AsyncCamoufox

    return AsyncCamoufox


async def launch_camoufox(
    headless: bool = True,
    os: str = "windows",
    **kwargs: Any,
) -> Any:
    """Создает и возвращает контекстный менеджер / сессию браузера AsyncCamoufox.

    Args:
        headless: Режим запуска без GUI (True) или с окном (False).
        os: Целевая ОС для подделки отпечатка ('windows', 'macos', 'linux').
        **kwargs: Дополнительные аргументы, передаваемые в конструктор AsyncCamoufox.

    Returns:
        Экземпляр AsyncCamoufox, готовый к использованию через async with.

    Raises:
        OptionalDependencyError: Если библиотека camoufox не установлена.
    """
    if not CAMOUFOX_AVAILABLE:
        raise OptionalDependencyError(
            "Для использования Camoufox требуется библиотека 'camoufox'.\n"
            "Установите её: pip install chutils[camoufox] или pip install camoufox",
            dependency="camoufox",
            hint="Выполните pip install camoufox",
        )

    camoufox_cls = get_async_camoufox_class()
    return camoufox_cls(headless=headless, os=os, **kwargs)
