"""Flask интеграция для валидации VKMA launchParams."""

from functools import wraps
from typing import Any, Callable

from chutils.vkma.exceptions import VKMAValidationError
from chutils.vkma.validator import parse_vkma_launch_params

try:
    from flask import g, jsonify, request
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


def require_vkma_auth(
    client_secret: str | None = None,
    max_age_seconds: int | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Декоратор Flask для авторизации вызовов из VK Mini App.

    Args:
        client_secret: Ключ приложения VK.
        max_age_seconds: Максимальный допустимый возраст подписи.

    Returns:
        Декоратор функции-обработчика Flask.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not HAS_FLASK:
                raise RuntimeError("Пакет flask не установлен. Установите chutils[vkma] или flask.")

            auth_header = request.headers.get("Authorization")
            raw_params: str | dict[str, Any] | None = None

            if auth_header and auth_header.startswith("Bearer "):
                raw_params = auth_header[7:].strip()
            elif "vk_user_id" in request.args:
                raw_params = dict(request.args)
            elif request.headers.get("X-VKMA-Init-Data"):
                raw_params = request.headers.get("X-VKMA-Init-Data")

            if not raw_params:
                return jsonify({"detail": "Отсутствуют параметры авторизации VKMA."}), 401

            try:
                vkma_params = parse_vkma_launch_params(
                    raw_params,
                    client_secret=client_secret,
                    max_age_seconds=max_age_seconds,
                )
                g.vkma_params = vkma_params
            except VKMAValidationError as exc:
                return jsonify({"detail": f"Ошибка авторизации VKMA: {exc.message}"}), 401

            return func(*args, **kwargs)

        return wrapper

    return decorator
