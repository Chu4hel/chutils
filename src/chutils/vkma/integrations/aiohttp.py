"""Aiohttp интеграция для валидации VKMA launchParams."""

from typing import Any, Callable

from chutils.vkma.exceptions import VKMAValidationError
from chutils.vkma.validator import parse_vkma_launch_params

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


def vkma_auth_middleware(
    client_secret: str | None = None,
    max_age_seconds: int | None = None,
    exclude_paths: set[str] | None = None,
) -> Any:
    """Фабрика Aiohttp `@web.middleware` для защиты роутов VK Mini Apps.

    Args:
        client_secret: Ключ приложения VK.
        max_age_seconds: Максимальное время жизни подписи.
        exclude_paths: Пути-исключения без проверки подписи.

    Returns:
        Объект Aiohttp middleware или None, если aiohttp не установлен.
    """
    if not HAS_AIOHTTP:
        return None

    excluded = exclude_paths or set()

    @web.middleware  # type: ignore[untyped-decorator]
    async def middleware(request: web.Request, handler: Callable[[web.Request], Any]) -> web.Response:
        if request.path in excluded:
            return await handler(request)

        auth_header = request.headers.get("Authorization")
        raw_params: str | dict[str, str] | None = None

        if auth_header and auth_header.startswith("Bearer "):
            raw_params = auth_header[7:].strip()
        elif "vk_user_id" in request.query:
            raw_params = dict(request.query)
        elif request.headers.get("X-VKMA-Init-Data"):
            raw_params = request.headers.get("X-VKMA-Init-Data")

        if not raw_params:
            return web.json_response({"detail": "Отсутствуют параметры авторизации VKMA."}, status=401)

        try:
            vkma_params = parse_vkma_launch_params(
                raw_params,
                client_secret=client_secret,
                max_age_seconds=max_age_seconds,
            )
            request["vkma_params"] = vkma_params
        except VKMAValidationError as exc:
            return web.json_response({"detail": f"Ошибка авторизации VKMA: {exc.message}"}, status=401)

        return await handler(request)

    return middleware
