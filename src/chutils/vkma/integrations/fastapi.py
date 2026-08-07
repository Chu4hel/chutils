"""FastAPI / Starlette интеграция для валидации VKMA launchParams / initData."""

from typing import Any, Callable, Sequence
from urllib.parse import unquote

from chutils.vkma.exceptions import VKMAValidationError
from chutils.vkma.models import VKMALaunchParams
from chutils.vkma.validator import parse_vkma_launch_params

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from fastapi import Depends, HTTPException, status
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    BaseHTTPMiddleware = object  # type: ignore[misc, assignment]
    Request = Any  # type: ignore[misc, assignment]
    Response = Any  # type: ignore[misc, assignment]


def _extract_vk_raw_params_from_request(request: Any) -> str | dict[str, Any] | None:
    """Извлекает launchParams из Authorization header, Query параметров или URL."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:].strip()
        if "vk_user_id=" in bearer_token:
            return bearer_token

    # Пробуем извлечь из Query string
    query_string = str(request.query_params)
    if "vk_user_id=" in query_string:
        return query_string

    # Пробуем извлечь из X-VKMA-Init-Data
    custom_header = request.headers.get("X-VKMA-Init-Data")
    if custom_header:
        return custom_header

    return None


if HAS_FASTAPI:
    class VKMAAuthMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
        """FastAPI / Starlette Middleware для автоматической валидации параметров VKMA."""

        def __init__(
            self,
            app: Any,
            client_secret: str | None = None,
            max_age_seconds: int | None = None,
            exclude_paths: Sequence[str] | None = None,
        ) -> None:
            super().__init__(app)
            self.client_secret = client_secret
            self.max_age_seconds = max_age_seconds
            self.exclude_paths = set(exclude_paths or [])

        async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
            if request.url.path in self.exclude_paths:
                return await call_next(request)

            raw_params = _extract_vk_raw_params_from_request(request)
            if not raw_params:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Отсутствуют параметры авторизации VKMA (initData / launchParams)."},
                )

            try:
                vkma_params = parse_vkma_launch_params(
                    raw_params,
                    client_secret=self.client_secret,
                    max_age_seconds=self.max_age_seconds,
                )
                request.state.vkma_params = vkma_params
            except VKMAValidationError as exc:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": f"Ошибка авторизации VKMA: {exc.message}"},
                )

            return await call_next(request)

    async def get_current_vkma_params(request: Request) -> VKMALaunchParams:
        """FastAPI Depends() хелпер для внедрения VKMALaunchParams в обработчик роута."""
        if hasattr(request.state, "vkma_params") and isinstance(request.state.vkma_params, VKMALaunchParams):
            return request.state.vkma_params

        raw_params = _extract_vk_raw_params_from_request(request)
        if not raw_params:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Параметры VKMA не найдены в запросе.",
            )

        try:
            return parse_vkma_launch_params(raw_params)
        except VKMAValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Недействительные параметры VKMA: {exc.message}",
            ) from exc
else:
    VKMAAuthMiddleware = None  # type: ignore[misc, assignment]
    get_current_vkma_params = None  # type: ignore[misc, assignment]
