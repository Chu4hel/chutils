"""
Модуль chutils.http.tls_client — HTTP-клиент с TLS/HTTP2 Client Impersonation на базе curl-cffi.

Предоставляет:
- `TLSSession` — синхронный клиент с маскировкой сетевого стека (JA3/JA4, HTTP/2).
- `TLSAsyncClient` — асинхронный клиент для высокопроизводительного скрапинга в обход WAF/Cloudflare.
- Автоматический fallback на стандартный HTTP-клиент при отсутствии curl-cffi.
- Полную интеграцию с ProxyPool и туннелями аутентификации прокси.
"""

from __future__ import annotations

import importlib.util
import types
from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from chutils.exceptions import OptionalDependencyError
from chutils.http.client import AsyncHttpClient, HttpClient
from chutils.http.fallback import HttpResponse
from chutils.logger import setup_logger

if TYPE_CHECKING:
    from chutils.scraping.proxy.models import ProxyConfig
    from chutils.scraping.proxy.pool import ProxyPool

logger = setup_logger(__name__)

DEFAULT_IMPERSONATE_PROFILE: str = "chrome120"
"""Профиль браузера по умолчанию для TLS Client Impersonation."""

CURL_CFFI_AVAILABLE: bool = importlib.util.find_spec("curl_cffi") is not None
"""Флаг доступности библиотеки curl-cffi."""


def _resolve_proxy_url(
    proxy: ProxyConfig | str | None,
    proxy_pool: ProxyPool | None,
) -> str | None:
    """Извлекает URL прокси-сервера из переданных параметров или пула.

    Args:
        proxy: Экземпляр ProxyConfig или строковый URL.
        proxy_pool: Пул прокси для автоматического получения следующего адреса.

    Returns:
        Строка URL прокси или None.
    """
    if proxy is not None:
        if hasattr(proxy, "url"):
            return str(proxy.url)
        return str(proxy)
    if proxy_pool is not None:
        p = proxy_pool.get_next()
        if p is not None:
            return str(p.url)
    return None


def create_curl_session(
    impersonate: str,
    proxy: str | None = None,
    **kwargs: Any,
) -> Any:
    """Создает синхронную сессию curl_cffi с заданным профилем impersonate.

    Args:
        impersonate: Имя профиля браузера (например, 'chrome120').
        proxy: URL прокси-сервера.
        **kwargs: Дополнительные параметры для Session.

    Returns:
        Экземпляр curl_cffi.requests.Session.
    """
    from curl_cffi import requests as curl_requests

    session_kwargs: dict[str, Any] = {"impersonate": impersonate, **kwargs}
    if proxy:
        session_kwargs["proxy"] = proxy
    return curl_requests.Session(**session_kwargs)


def create_curl_async_session(
    impersonate: str,
    proxy: str | None = None,
    **kwargs: Any,
) -> Any:
    """Создает асинхронную сессию curl_cffi с заданным профилем impersonate.

    Args:
        impersonate: Имя профиля браузера (например, 'chrome120').
        proxy: URL прокси-сервера.
        **kwargs: Дополнительные параметры для AsyncSession.

    Returns:
        Экземпляр curl_cffi.requests.AsyncSession.
    """
    from curl_cffi import requests as curl_requests

    session_kwargs: dict[str, Any] = {"impersonate": impersonate, **kwargs}
    if proxy:
        session_kwargs["proxy"] = proxy
    return curl_requests.AsyncSession(**session_kwargs)


def _curl_resp_to_http_response(resp: Any) -> HttpResponse:
    """Конвертирует ответ curl_cffi.Response в унифицированный HttpResponse.

    Args:
        resp: Объект ответа curl_cffi.

    Returns:
        Экземпляр HttpResponse.
    """
    headers = dict(resp.headers) if hasattr(resp, "headers") else {}
    elapsed = (
        float(resp.elapsed)
        if hasattr(resp, "elapsed") and resp.elapsed is not None
        else 0.0
    )
    return HttpResponse(
        status_code=int(resp.status_code),
        headers=headers,
        content=bytes(resp.content),
        elapsed=elapsed,
        url=str(resp.url),
    )


class TLSSession:
    """Синхронный HTTP-клиент с поддержкой TLS/HTTP2 Client Impersonation (curl-cffi)."""

    def __init__(
        self,
        impersonate: str = DEFAULT_IMPERSONATE_PROFILE,
        proxy: ProxyConfig | str | None = None,
        proxy_pool: ProxyPool | None = None,
        fallback_to_standard: bool = False,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        """Инициализирует TLSSession.

        Args:
            impersonate: Профиль маскировки браузера (напр. 'chrome120', 'safari17_0').
            proxy: Прокси-сервер (ProxyConfig или строка).
            proxy_pool: Пул прокси chutils.
            fallback_to_standard: Флаг автоматического отката на HttpClient при отсутствии curl-cffi.
            timeout: Таймаут запросов в секундах.
            **kwargs: Дополнительные параметры конфигурации.

        Raises:
            OptionalDependencyError: Если curl-cffi отсутствует и fallback_to_standard=False.
        """
        self.impersonate: str = impersonate
        self.timeout: float = timeout
        self.is_fallback: bool = False
        self._standard_client: HttpClient | None = None
        self._session: Any = None

        proxy_url = _resolve_proxy_url(proxy, proxy_pool)

        if not CURL_CFFI_AVAILABLE:
            if fallback_to_standard:
                self.is_fallback = True
                logger.warning(
                    "Библиотека 'curl-cffi' не установлена. Используется fallback на HttpClient (httpx/urllib). "
                    "TLS Impersonation отключен. Установите: pip install 'chutils[tls]'"
                )
                self._standard_client = HttpClient(timeout=timeout, **kwargs)
                return
            raise OptionalDependencyError(
                "Для работы TLS Client Impersonation требуется библиотека 'curl-cffi'.\n"
                "Установите её: pip install 'chutils[tls]'",
                dependency="curl-cffi",
            )

        self._session = create_curl_session(
            impersonate=impersonate, proxy=proxy_url, **kwargs
        )

    def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет синхронный HTTP-запрос.

        Args:
            method: HTTP метод (GET, POST, etc.).
            url: Целевой URL.
            **kwargs: Параметры запроса (headers, params, data, json, timeout).

        Returns:
            Унифицированный объект ответа HttpResponse.
        """
        if self.is_fallback and self._standard_client is not None:
            effective_url = url
            params = kwargs.get("params")
            if params:
                import urllib.parse

                query_str = urllib.parse.urlencode(params)
                delimiter = "&" if "?" in effective_url else "?"
                effective_url = f"{effective_url}{delimiter}{query_str}"
            headers = kwargs.get("headers")
            timeout = kwargs.get("timeout", self.timeout)
            json_data = kwargs.get("json_data", kwargs.get("json"))
            data = kwargs.get("data")
            return self._standard_client.request(
                method,
                effective_url,
                headers=headers,
                json_data=json_data,
                data=data,
                timeout=timeout,
            )

        kwargs.setdefault("timeout", self.timeout)
        resp = self._session.request(method=method, url=url, **kwargs)
        return _curl_resp_to_http_response(resp)

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет GET запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет POST запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет PUT запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет DELETE запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("DELETE", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет PATCH запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("PATCH", url, **kwargs)

    def close(self) -> None:
        """Закрывает базовую сессию."""
        if self._standard_client is not None:
            self._standard_client.close()
        elif self._session is not None and hasattr(self._session, "close"):
            self._session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.close()


class TLSAsyncClient:
    """Асинхронный HTTP-клиент с поддержкой TLS/HTTP2 Client Impersonation (curl-cffi)."""

    def __init__(
        self,
        impersonate: str = DEFAULT_IMPERSONATE_PROFILE,
        proxy: ProxyConfig | str | None = None,
        proxy_pool: ProxyPool | None = None,
        fallback_to_standard: bool = False,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        """Инициализирует TLSAsyncClient.

        Args:
            impersonate: Профиль маскировки браузера (напр. 'chrome120', 'safari17_0').
            proxy: Прокси-сервер (ProxyConfig или строка).
            proxy_pool: Пул прокси chutils.
            fallback_to_standard: Флаг автоматического отката на AsyncHttpClient при отсутствии curl-cffi.
            timeout: Таймаут запросов в секундах.
            **kwargs: Дополнительные параметры конфигурации.

        Raises:
            OptionalDependencyError: Если curl-cffi отсутствует и fallback_to_standard=False.
        """
        self.impersonate: str = impersonate
        self.timeout: float = timeout
        self.is_fallback: bool = False
        self._standard_client: AsyncHttpClient | None = None
        self._session: Any = None

        proxy_url = _resolve_proxy_url(proxy, proxy_pool)

        if not CURL_CFFI_AVAILABLE:
            if fallback_to_standard:
                self.is_fallback = True
                logger.warning(
                    "Библиотека 'curl-cffi' не установлена. Используется fallback на AsyncHttpClient (httpx). "
                    "TLS Impersonation отключен. Установите: pip install 'chutils[tls]'"
                )
                self._standard_client = AsyncHttpClient(timeout=timeout, **kwargs)
                return
            raise OptionalDependencyError(
                "Для работы TLS Client Impersonation требуется библиотека 'curl-cffi'.\n"
                "Установите её: pip install 'chutils[tls]'",
                dependency="curl-cffi",
            )

        self._session = create_curl_async_session(
            impersonate=impersonate, proxy=proxy_url, **kwargs
        )

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет асинхронный HTTP-запрос.

        Args:
            method: HTTP метод (GET, POST, etc.).
            url: Целевой URL.
            **kwargs: Параметры запроса (headers, params, data, json, timeout).

        Returns:
            Унифицированный объект ответа HttpResponse.
        """
        if self.is_fallback and self._standard_client is not None:
            effective_url = url
            params = kwargs.get("params")
            if params:
                import urllib.parse

                query_str = urllib.parse.urlencode(params)
                delimiter = "&" if "?" in effective_url else "?"
                effective_url = f"{effective_url}{delimiter}{query_str}"
            headers = kwargs.get("headers")
            timeout = kwargs.get("timeout", self.timeout)
            json_data = kwargs.get("json_data", kwargs.get("json"))
            data = kwargs.get("data")
            return await self._standard_client.request(
                method,
                effective_url,
                headers=headers,
                json_data=json_data,
                data=data,
                timeout=timeout,
            )

        kwargs.setdefault("timeout", self.timeout)
        resp = await self._session.request(method=method, url=url, **kwargs)
        return _curl_resp_to_http_response(resp)

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет асинхронный GET запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет асинхронный POST запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет асинхронный PUT запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет асинхронный DELETE запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> HttpResponse:
        """Выполняет асинхронный PATCH запрос.

        Args:
            url: Целевой URL.
            **kwargs: Дополнительные параметры запроса.

        Returns:
            Объект HttpResponse.
        """
        return await self.request("PATCH", url, **kwargs)

    async def aclose(self) -> None:
        """Закрывает асинхронную сессию."""
        if self._standard_client is not None:
            await self._standard_client.aclose()
        elif self._session is not None and hasattr(self._session, "close"):
            await self._session.close()

    async def close(self) -> None:
        """Псевдоним для aclose."""
        await self.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        await self.aclose()
