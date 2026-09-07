"""
Модуль chutils.http.async_client — AsyncHttpClient.

Предоставляет:
- `AsyncHttpClient` — асинхронный HTTP-клиент на httpx (требует httpx).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from . import client
from .fallback import HttpResponse

if TYPE_CHECKING:
    from .resilience import ResiliencePolicy


# ─── AsyncHttpClient ──────────────────────────────────────────────────────────


class AsyncHttpClient:
    """Асинхронный HTTP-клиент на базе httpx.AsyncClient.

    Требует установленного `httpx`. При его отсутствии вызывает
    `OptionalDependencyError` при инициализации.

    Args:
        base_url: Базовый URL-префикс для всех запросов.
        default_headers: Заголовки по умолчанию.
        timeout: Таймаут запросов в секундах.
        policy: Политика отказоустойчивости.
        sensitive_headers: Дополнительные заголовки для маскирования.

    Example:
        ```python
        from chutils.http import AsyncHttpClient, ResiliencePolicy

        policy = ResiliencePolicy(retries=2, timeout=5.0)
        async with AsyncHttpClient(
            base_url="https://api.example.com", policy=policy
        ) as client:
            resp = await client.get("/status")
            resp.raise_for_status()
        ```
    """

    def __init__(
            self,
            *,
            base_url: str = "",
            default_headers: dict[str, str] | None = None,
            timeout: float | None = 30.0,
            policy: ResiliencePolicy | None = None,
            sensitive_headers: set[str] | None = None,
    ) -> None:
        """Инициализирует AsyncHttpClient.

        Args:
            base_url: Базовый URL для всех запросов.
            default_headers: Заголовки по умолчанию.
            timeout: Таймаут в секундах.
            policy: Политика отказоустойчивости.
            sensitive_headers: Имена заголовков для маскирования.

        Raises:
            OptionalDependencyError: Если httpx не установлен.
        """
        if not client.HTTPX_AVAILABLE or client.httpx is None:
            from chutils.exceptions import OptionalDependencyError

            raise OptionalDependencyError(
                "AsyncHttpClient требует httpx.",
                dependency="httpx",
                hint="Установите его: pip install chutils[http]",
            )

        self.base_url = base_url.rstrip("/")
        self.default_headers: dict[str, str] = default_headers or {}
        self.timeout = timeout
        self.policy = policy
        self._extra_sensitive: frozenset[str] = frozenset(
            h.lower() for h in (sensitive_headers or set())
        )
        self._async_client: Any = None  # httpx.AsyncClient

    def _build_url(self, path: str) -> str:
        """Строит полный URL.

        Args:
            path: Путь или абсолютный URL.

        Returns:
            Полный URL.
        """
        if path.startswith(("http://", "https://")):
            return path
        return self.base_url + "/" + path.lstrip("/") if self.base_url else path

    async def request(
            self,
            method: str,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            json_data: object | None = None,
            data: bytes | str | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет асинхронный HTTP-запрос.

        Args:
            method: HTTP-метод (GET, POST, PUT, DELETE, PATCH).
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            json_data: Данные для JSON-тела.
            data: Сырое тело запроса.
            timeout: Таймаут для этого конкретного запроса.

        Returns:
            Объект HttpResponse.
        """
        assert client.httpx is not None

        url = self._build_url(path)
        effective_timeout = timeout if timeout is not None else self.timeout
        merged_headers = {**self.default_headers, **(headers or {})}

        client._get_log().debug(
            "→ async %s %s  headers=%s",
            method.upper(),
            url,
            client._mask_headers(merged_headers, self._extra_sensitive),
        )

        async def _call() -> HttpResponse:
            assert client.httpx is not None
            if self._async_client is not None:
                raw = await self._async_client.request(
                    method.upper(),
                    url,
                    headers=merged_headers,
                    json=json_data,
                    content=data
                    if isinstance(data, bytes)
                    else (data.encode() if data else None),
                    timeout=effective_timeout,
                )
            else:
                async with client.httpx.AsyncClient(
                        timeout=effective_timeout
                ) as ahx:
                    raw = await ahx.request(
                        method.upper(),
                        url,
                        headers=merged_headers,
                        json=json_data,
                        content=data
                        if isinstance(data, bytes)
                        else (data.encode() if data else None),
                    )
            return client._httpx_to_response(raw)

        if self.policy is not None:
            resp = await self.policy.apply_async(_call)
        else:
            resp = await _call()

        assert isinstance(resp, HttpResponse)

        client._get_log().debug(
            "← async %s %s  status=%d  elapsed=%.3fs",
            method.upper(),
            url,
            resp.status_code,
            resp.elapsed,
        )
        return resp

    async def get(
            self,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет async GET-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request("GET", path, headers=headers, timeout=timeout)

    async def post(
            self,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            json_data: object | None = None,
            data: bytes | str | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет async POST-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            json_data: Данные для JSON-тела.
            data: Сырое тело.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request(
            "POST",
            path,
            headers=headers,
            json_data=json_data,
            data=data,
            timeout=timeout,
        )

    async def put(
            self,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            json_data: object | None = None,
            data: bytes | str | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет async PUT-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            json_data: Данные для JSON-тела.
            data: Сырое тело.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request(
            "PUT",
            path,
            headers=headers,
            json_data=json_data,
            data=data,
            timeout=timeout,
        )

    async def delete(
            self,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет async DELETE-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request("DELETE", path, headers=headers, timeout=timeout)

    async def patch(
            self,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            json_data: object | None = None,
            data: bytes | str | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет async PATCH-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            json_data: Данные для JSON-тела.
            data: Сырое тело.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request(
            "PATCH",
            path,
            headers=headers,
            json_data=json_data,
            data=data,
            timeout=timeout,
        )

    async def aclose(self) -> None:
        """Закрывает async-клиент и освобождает ресурсы."""
        if self._async_client is not None:
            try:
                await self._async_client.aclose()
            except Exception:
                pass
            self._async_client = None

    async def __aenter__(self) -> Self:
        """Поддержка async-контекстного менеджера.

        Returns:
            Сам экземпляр клиента.
        """
        assert client.httpx is not None
        self._async_client = client.httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.default_headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        """Закрывает async-клиент при выходе из контекстного менеджера."""
        await self.aclose()
