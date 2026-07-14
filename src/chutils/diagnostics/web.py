from __future__ import annotations

from collections.abc import Callable, Awaitable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse
    from flask import Response
    from .manager import DiagnosticsManager


def get_fastapi_health_handler(
        manager: DiagnosticsManager
) -> Callable[[], Awaitable[JSONResponse]]:
    """Создает асинхронный обработчик здоровья для FastAPI.

    Args:
        manager: Менеджер диагностики, выполняющий проверки.

    Returns:
        Асинхронная функция-обработчик, возвращающая JSONResponse.

    Raises:
        RuntimeError: Если библиотека fastapi не установлена.
    """
    try:
        from fastapi import status
        from fastapi.responses import JSONResponse
    except ImportError as e:
        raise RuntimeError(
            "FastAPI не установлен. Для использования этого хелпера установите fastapi."
        ) from e

    async def health_handler() -> JSONResponse:
        report = await manager.run_checks()
        report_data = report.model_dump()

        status_code = status.HTTP_200_OK
        if report.status == "UNHEALTHY":
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return JSONResponse(content=report_data, status_code=status_code)

    return health_handler


def get_flask_health_handler(
        manager: DiagnosticsManager
) -> Callable[[], Response]:
    """Создает синхронный обработчик здоровья для Flask.

    Args:
        manager: Менеджер диагностики, выполняющий проверки.

    Returns:
        Функция-обработчик, возвращающая Flask Response.

    Raises:
        RuntimeError: Если библиотека flask не установлена.
    """
    try:
        from flask import jsonify, make_response
    except ImportError as e:
        raise RuntimeError(
            "Flask не установлен. Для использования этого хелпера установите flask."
        ) from e

    def health_handler() -> Any:
        report = manager.run_checks_sync()
        report_data = report.model_dump()

        status_code = 200
        if report.status == "UNHEALTHY":
            status_code = 503

        # Возвращаем объект ответа Flask
        return make_response(jsonify(report_data), status_code)

    return health_handler
