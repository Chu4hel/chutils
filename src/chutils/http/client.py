"""
Модуль chutils.http.client — HttpClient и AsyncHttpClient.

Предоставляет:
- `HttpClient` — синхронный HTTP-клиент на httpx (с fallback на urllib при отсутствии httpx).
- `AsyncHttpClient` — асинхронный HTTP-клиент на httpx (требует httpx).

Оба клиента поддерживают:
- Интеграцию с `ResiliencePolicy` (retry, timeout, semaphore, circuit breaker).
- Автоматическое маскирование чувствительных заголовков в логах.
- Контекстные менеджеры (with / async with).
- JSON-тело запроса и ответа.
"""
from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Optional

from .fallback import HttpResponse, UrllibFallbackClient, _SENSITIVE_HEADERS

if TYPE_CHECKING:
    from .resilience import ResiliencePolicy
    from chutils.logger import ChutilsLogger

# ─── Проверка доступности httpx ──────────────────────────────────────────────

HTTPX_AVAILABLE: bool = importlib.util.find_spec("httpx") is not None

# Lazy-импорт httpx (только если доступен)
if HTTPX_AVAILABLE:
    try:
        import httpx  # type: ignore[import-untyped]
    except ImportError:
        httpx = None  # type: ignore[assignment]
        HTTPX_AVAILABLE = False
else:
    httpx = None  # type: ignore[assignment]

# Флаг для единоразового предупреждения о fallback
_FALLBACK_WARNING_EMITTED: bool = False

# ─── Ленивый логгер ──────────────────────────────────────────────────────────

_module_logger: Optional["ChutilsLogger"] = None


def _get_log() -> "ChutilsLogger":
    """Возвращает лениво инициализированный логгер модуля.

    Returns:
        Экземпляр ChutilsLogger.
    """
    global _module_logger
    if _module_logger is None:
        from chutils import logger as chutils_logger
        _module_logger = chutils_logger.setup_logger(__name__)
    if _module_logger is None:
        raise RuntimeError("Не удалось инициализировать логгер chutils.http.client")
    return _module_logger


# ─── Хелпер: конвертация httpx.Response → HttpResponse ──────────────────────


def _httpx_to_response(resp: object) -> HttpResponse:
    """Конвертирует httpx.Response в унифицированный HttpResponse.

    Args:
        resp: Экземпляр httpx.Response.

    Returns:
        Объект HttpResponse.
    """
    # Используем duck-typing чтобы избежать прямого импорта httpx в аннотациях
    return HttpResponse(
        status_code=resp.status_code,  # type: ignore[union-attr]
        headers=dict(resp.headers),  # type: ignore[union-attr]
        content=resp.content,  # type: ignore[union-attr]
        elapsed=resp.elapsed.total_seconds(),  # type: ignore[union-attr]
        url=str(resp.url),  # type: ignore[union-attr]
    )


def _mask_headers(headers: dict[str, str], extra: frozenset[str]) -> dict[str, str]:
    """Маскирует чувствительные заголовки для логирования.

    Args:
        headers: Исходный словарь заголовков.
        extra: Дополнительные имена заголовков для маскирования.

    Returns:
        Копия словаря с заменёнными значениями.
    """
    return {
        k: "[MASKED]" if k.lower() in _SENSITIVE_HEADERS or k.lower() in extra else v
        for k, v in headers.items()
    }


# ─── HttpClient ───────────────────────────────────────────────────────────────


class HttpClient:
    """Синхронный HTTP-клиент с батареями (httpx + fallback на urllib).

    При наличии `httpx` использует его как транспорт. При отсутствии —
    прозрачно переключается на встроенный `urllib.request`, выводя
    единоразовое предупреждение в лог.

    Args:
        base_url: Базовый URL-префикс для всех запросов.
        default_headers: Заголовки, добавляемые к каждому запросу.
        timeout: Таймаут запросов по умолчанию в секундах.
        policy: Политика отказоустойчивости (retry, semaphore и т.д.).
        sensitive_headers: Дополнительные заголовки для маскирования в логах.

    Example:
        ```python
        from chutils.http import HttpClient, ResiliencePolicy

        policy = ResiliencePolicy(retries=3, timeout=10.0)
        with HttpClient(base_url="https://api.example.com", policy=policy) as client:
            resp = client.get("/users/1")
            resp.raise_for_status()
            data = resp.json()
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
        """Инициализирует HttpClient.

        Args:
            base_url: Базовый URL для всех запросов.
            default_headers: Заголовки по умолчанию для каждого запроса.
            timeout: Таймаут в секундах.
            policy: Политика отказоустойчивости.
            sensitive_headers: Имена заголовков для маскирования в логах.
        """
        self.base_url = base_url.rstrip("/")
        self.default_headers: dict[str, str] = default_headers or {}
        self.timeout = timeout
        self.policy = policy
        self._extra_sensitive: frozenset[str] = frozenset(
            h.lower() for h in (sensitive_headers or set())
        )
        self._fallback: UrllibFallbackClient | None = None
        self._httpx_client: object | None = None  # httpx.Client instance

    def _get_fallback_client(self) -> UrllibFallbackClient:
        """Возвращает (или создаёт) fallback-клиент на urllib.

        Returns:
            Экземпляр UrllibFallbackClient.
        """
        if self._fallback is None:
            self._fallback = UrllibFallbackClient(
                base_url=self.base_url,
                default_headers=self.default_headers,
                timeout=self.timeout,
                policy=self.policy,
                sensitive_headers=set(self._extra_sensitive),
            )
        return self._fallback

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

    def _emit_fallback_warning(self) -> None:
        """Логирует предупреждение о переходе на urllib (единоразово)."""
        global _FALLBACK_WARNING_EMITTED
        if not _FALLBACK_WARNING_EMITTED:
            _FALLBACK_WARNING_EMITTED = True
            _get_log().warning(
                "httpx не установлен. HttpClient использует urllib fallback. "
                "Установите httpx для полной функциональности: pip install chutils[http]"
            )

    def request(
            self,
            method: str,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            json_data: object | None = None,
            data: bytes | str | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет HTTP-запрос.

        Args:
            method: HTTP-метод (GET, POST, PUT, DELETE, PATCH).
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            json_data: Данные для JSON-тела запроса.
            data: Сырое тело запроса (bytes или str).
            timeout: Таймаут для этого конкретного запроса.

        Returns:
            Объект HttpResponse.
        """
        if not HTTPX_AVAILABLE or httpx is None:
            self._emit_fallback_warning()
            return self._get_fallback_client().request(
                method, path,
                headers=headers,
                json_data=json_data,
                data=data,
                timeout=timeout,
            )

        url = self._build_url(path)
        effective_timeout = timeout if timeout is not None else self.timeout
        merged_headers = {**self.default_headers, **(headers or {})}

        _get_log().debug(
            "→ %s %s  headers=%s",
            method.upper(),
            url,
            _mask_headers(merged_headers, self._extra_sensitive),
        )

        def _call() -> HttpResponse:
            assert httpx is not None  # noqa: S101
            if self._httpx_client is not None:
                raw = self._httpx_client.request(  # type: ignore[union-attr]
                    method.upper(),
                    url,
                    headers=merged_headers,
                    json=json_data,
                    content=data if isinstance(data, bytes) else (data.encode() if data else None),
                    timeout=effective_timeout,
                )
            else:
                with httpx.Client(timeout=effective_timeout) as hx:
                    raw = hx.request(
                        method.upper(),
                        url,
                        headers=merged_headers,
                        json=json_data,
                        content=data if isinstance(data, bytes) else (data.encode() if data else None),
                    )
            return _httpx_to_response(raw)

        if self.policy is not None:
            resp = self.policy.apply_sync(_call)
        else:
            resp = _call()

        assert isinstance(resp, HttpResponse)  # noqa: S101

        _get_log().debug(
            "← %s %s  status=%d  elapsed=%.3fs",
            method.upper(),
            url,
            resp.status_code,
            resp.elapsed,
        )
        return resp

    def get(self, path: str, *, headers: dict[str, str] | None = None, timeout: float | None = None) -> HttpResponse:
        """Выполняет GET-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("GET", path, headers=headers, timeout=timeout)

    def post(
            self,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            json_data: object | None = None,
            data: bytes | str | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет POST-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            json_data: Данные для JSON-тела.
            data: Сырое тело.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("POST", path, headers=headers, json_data=json_data, data=data, timeout=timeout)

    def put(
            self,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            json_data: object | None = None,
            data: bytes | str | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет PUT-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            json_data: Данные для JSON-тела.
            data: Сырое тело.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("PUT", path, headers=headers, json_data=json_data, data=data, timeout=timeout)

    def delete(self, path: str, *, headers: dict[str, str] | None = None, timeout: float | None = None) -> HttpResponse:
        """Выполняет DELETE-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("DELETE", path, headers=headers, timeout=timeout)

    def patch(
            self,
            path: str,
            *,
            headers: dict[str, str] | None = None,
            json_data: object | None = None,
            data: bytes | str | None = None,
            timeout: float | None = None,
    ) -> HttpResponse:
        """Выполняет PATCH-запрос.

        Args:
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки.
            json_data: Данные для JSON-тела.
            data: Сырое тело.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("PATCH", path, headers=headers, json_data=json_data, data=data, timeout=timeout)

    def close(self) -> None:
        """Закрывает клиент и освобождает ресурсы."""
        if self._httpx_client is not None:
            try:
                self._httpx_client.close()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
            self._httpx_client = None
        if self._fallback is not None:
            self._fallback.close()

    def __enter__(self) -> HttpClient:
        """Поддержка контекстного менеджера.

        Returns:
            Сам экземпляр клиента.
        """
        if HTTPX_AVAILABLE and httpx is not None:
            self._httpx_client = httpx.Client(
                base_url=self.base_url,
                headers=self.default_headers,
                timeout=self.timeout,
            )
        return self

    def __exit__(self, *args: object) -> None:
        """Закрывает клиент при выходе из контекстного менеджера."""
        self.close()


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
        async with AsyncHttpClient(base_url="https://api.example.com", policy=policy) as client:
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
        if not HTTPX_AVAILABLE or httpx is None:
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
        self._async_client: object | None = None  # httpx.AsyncClient

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
        assert httpx is not None  # noqa: S101

        url = self._build_url(path)
        effective_timeout = timeout if timeout is not None else self.timeout
        merged_headers = {**self.default_headers, **(headers or {})}

        _get_log().debug(
            "→ async %s %s  headers=%s",
            method.upper(),
            url,
            _mask_headers(merged_headers, self._extra_sensitive),
        )

        async def _call() -> HttpResponse:
            assert httpx is not None  # noqa: S101
            if self._async_client is not None:
                raw = await self._async_client.request(  # type: ignore[union-attr]
                    method.upper(),
                    url,
                    headers=merged_headers,
                    json=json_data,
                    content=data if isinstance(data, bytes) else (data.encode() if data else None),
                    timeout=effective_timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=effective_timeout) as ahx:
                    raw = await ahx.request(
                        method.upper(),
                        url,
                        headers=merged_headers,
                        json=json_data,
                        content=data if isinstance(data, bytes) else (data.encode() if data else None),
                    )
            return _httpx_to_response(raw)

        if self.policy is not None:
            resp = await self.policy.apply_async(_call)
        else:
            resp = await _call()

        assert isinstance(resp, HttpResponse)  # noqa: S101

        _get_log().debug(
            "← async %s %s  status=%d  elapsed=%.3fs",
            method.upper(),
            url,
            resp.status_code,
            resp.elapsed,
        )
        return resp

    async def get(self, path: str, *, headers: dict[str, str] | None = None,
                  timeout: float | None = None) -> HttpResponse:
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
        return await self.request("POST", path, headers=headers, json_data=json_data, data=data, timeout=timeout)

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
        return await self.request("PUT", path, headers=headers, json_data=json_data, data=data, timeout=timeout)

    async def delete(self, path: str, *, headers: dict[str, str] | None = None,
                     timeout: float | None = None) -> HttpResponse:
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
        return await self.request("PATCH", path, headers=headers, json_data=json_data, data=data, timeout=timeout)

    async def aclose(self) -> None:
        """Закрывает async-клиент и освобождает ресурсы."""
        if self._async_client is not None:
            try:
                await self._async_client.aclose()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
            self._async_client = None

    async def __aenter__(self) -> AsyncHttpClient:
        """Поддержка async-контекстного менеджера.

        Returns:
            Сам экземпляр клиента.
        """
        assert httpx is not None  # noqa: S101
        self._async_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.default_headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        """Закрывает async-клиент при выходе из контекстного менеджера."""
        await self.aclose()
