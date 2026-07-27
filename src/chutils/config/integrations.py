"""
Интеграции Webhook с веб-фреймворками FastAPI и Flask.
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
from collections.abc import Callable
from typing import Any

from chutils.exceptions import OptionalDependencyError
from .manager import _cm
from .webhook_server import verify_webhook_request

logger = logging.getLogger(__name__)


def create_fastapi_webhook_route(
    secret_token: str | None = None,
    hmac_secret: str | None = None,
    on_reload: Callable[[], None] | None = None,
) -> Callable[..., Any]:
    """
    Создает асинхронный хэндлер для FastAPI/Starlette для приемки Webhook-уведомлений.

    Args:
        secret_token: Опциональный токен авторизации.
        hmac_secret: Опциональный секретный ключ HMAC-SHA256.
        on_reload: Колбэк для перезагрузки (по умолчанию _cm.trigger_reload).

    Returns:
        Асинхронная функция-хэндлер для роутера FastAPI.

    Raises:
        OptionalDependencyError: Если библиотека fastapi не установлена.
    """
    try:
        from fastapi import HTTPException, Request, Response
    except ImportError:
        raise OptionalDependencyError(
            "Для использования FastAPI Webhook необходимо установить пакет 'fastapi'.",
            package_name="fastapi",
        )

    callback = on_reload or _cm.trigger_reload

    async def webhook_endpoint(request: Request) -> Response:
        body = await request.body()
        headers_dict = {k: str(v) for k, v in request.headers.items()}

        valid, status_code, message = verify_webhook_request(
            headers=headers_dict,
            body=body,
            secret_token=secret_token,
            hmac_secret=hmac_secret,
        )

        if not valid:
            raise HTTPException(status_code=status_code, detail=message)

        try:
            callback()
        except Exception as err:
            logger.error("Ошибка перезагрузки конфига в FastAPI Webhook: %s", err)
            raise HTTPException(status_code=500, detail="Config reload failed")

        return Response(content='{"status": "reloaded"}', media_type="application/json")

    return webhook_endpoint


def create_flask_webhook_route(
    secret_token: str | None = None,
    hmac_secret: str | None = None,
    on_reload: Callable[[], None] | None = None,
) -> Callable[..., Any]:
    """
    Создает синхронную функцию-хэндлер для Flask роута.

    Args:
        secret_token: Опциональный токен авторизации.
        hmac_secret: Опциональный секретный ключ HMAC-SHA256.
        on_reload: Колбэк для перезагрузки (по умолчанию _cm.trigger_reload).

    Returns:
        Синхронная функция-представление (view function) для Flask.

    Raises:
        OptionalDependencyError: Если библиотека flask не установлена.
    """
    try:
        import flask
    except ImportError:
        raise OptionalDependencyError(
            "Для использования Flask Webhook необходимо установить пакет 'flask'.",
            package_name="flask",
        )

    callback = on_reload or _cm.trigger_reload

    def webhook_view() -> tuple[object, int]:
        request = flask.request
        body = request.get_data()
        headers_dict = {k: str(v) for k, v in request.headers.items()}

        valid, status_code, message = verify_webhook_request(
            headers=headers_dict,
            body=body,
            secret_token=secret_token,
            hmac_secret=hmac_secret,
        )

        if not valid:
            return flask.jsonify({"error": message}), status_code

        try:
            callback()
        except Exception as err:
            logger.error("Ошибка перезагрузки конфига во Flask Webhook: %s", err)
            return flask.jsonify({"error": "Config reload failed"}), 500

        return flask.jsonify({"status": "reloaded"}), 200

    return webhook_view
