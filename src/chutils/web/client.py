import asyncio
import logging
import time
from typing import Any, cast

import httpx
from httpx._utils import URLPattern

from chutils.cache import InMemoryCacheBackend
from chutils.decorators import get_limiter
from chutils.exceptions import RateLimitExceededError
from .proxy_pool import ProxyPool
from .user_agent import UserAgentRotator

logger = logging.getLogger(__name__)


class WebClient(httpx.Client):
    """Синхронный HTTP-клиент с поддержкой ротации User-Agent, прокси-пулов,

    лимитирования частоты и кэширования GET-запросов.
    """

    def __init__(
            self,
            *args: Any,
            user_agent_rotator: UserAgentRotator | None = None,
            proxy_pool: ProxyPool | None = None,
            rotate_ua: bool = True,
            rotate_proxy: bool = True,
            retries: int = 0,
            retry_delay: float = 1.0,
            retry_backoff: float = 2.0,
            retry_on_5xx: bool = True,
            rate_limit_calls: int | None = None,
            rate_limit_period: float = 1.0,
            rate_limit_strategy: str = "token_bucket",
            rate_limit_wait: bool = False,
            cache_ttl: int | None = None,
            cache_backend: Any | None = None,
            **kwargs: Any,
    ) -> None:
        """Инициализирует WebClient.

        Args:
            user_agent_rotator: Ротатор User-Agent.
            proxy_pool: Менеджер пула прокси.
            rotate_ua: Включить ли ротацию User-Agent.
            rotate_proxy: Включить ли смену прокси при ошибках.
            retries: Количество повторов при ошибках.
            retry_delay: Базовая задержка между попытками в секундах.
            retry_backoff: Множитель задержки.
            retry_on_5xx: Считать ли 5xx ошибки сбоем для повтора.
            rate_limit_calls: Ограничение количества запросов к хосту.
            rate_limit_period: Период ограничения в секундах.
            rate_limit_strategy: Стратегия лимитирования ('token_bucket' или 'leaky_bucket').
            rate_limit_wait: Ждать ли освобождения токена (или вызывать исключение).
            cache_ttl: Время жизни кэша GET-запросов в секундах.
            cache_backend: Бэкенд кэша.
        """
        self.user_agent_rotator: UserAgentRotator = (
                user_agent_rotator or UserAgentRotator()
        )
        self.proxy_pool: ProxyPool | None = proxy_pool
        self._rotate_ua_enabled: bool = rotate_ua
        self._rotate_proxy_enabled: bool = rotate_proxy

        self._retries: int = retries
        self._retry_delay: float = retry_delay
        self._retry_backoff: float = retry_backoff
        self._retry_on_5xx: bool = retry_on_5xx

        self._rate_limit_calls: int | None = rate_limit_calls
        self._rate_limit_period: float = rate_limit_period
        self._rate_limit_strategy: str = rate_limit_strategy
        self._rate_limit_wait: bool = rate_limit_wait

        self._cache_ttl: int | None = cache_ttl
        self._cache_backend: InMemoryCacheBackend[Any] = (
                cache_backend or InMemoryCacheBackend()
        )

        # Сохраняем аргументы транспорта для пересоздания
        self._transport_kwargs: dict[str, Any] = {
            "verify": kwargs.get("verify", True),
            "cert": kwargs.get("cert", None),
            "http1": kwargs.get("http1", True),
            "http2": kwargs.get("http2", False),
            "limits": kwargs.get("limits", httpx.Limits()),
            "trust_env": kwargs.get("trust_env", True),
        }

        # Первичная установка прокси
        if self.proxy_pool and "proxy" not in kwargs and "proxies" not in kwargs:
            p = self.proxy_pool.get_next_proxy()
            if p:
                kwargs["proxy"] = p

        super().__init__(*args, **kwargs)

    def rotate_proxy(self) -> None:
        """Переключает текущий клиент на следующий прокси из пула."""
        if not self.proxy_pool:
            return

        p = self.proxy_pool.get_next_proxy()
        if not p:
            return

        # Закрываем старые транспорты
        for transport in self._mounts.values():
            if transport is not None:
                transport.close()

        # Создаем новое прокси-подключение
        proxy_map = self._get_proxy_map(p, allow_env_proxies=False)
        self._mounts = {
            URLPattern(key): None
            if proxy is None
            else self._init_proxy_transport(proxy, **self._transport_kwargs)
            for key, proxy in proxy_map.items()
        }
        self._mounts = dict(sorted(self._mounts.items()))

    def send(
            self, request: httpx.Request, *args: Any, **kwargs: Any
    ) -> httpx.Response:
        """Перехватывает отправку запроса для ротации, лимитов и кэширования."""
        # 1. Rate Limit
        if self._rate_limit_calls:
            limit_key = f"web_host_{request.url.host}"
            limiter = get_limiter(
                limit_key,
                self._rate_limit_calls,
                self._rate_limit_period,
                self._rate_limit_strategy,
            )
            wait_time = limiter.acquire(wait=self._rate_limit_wait)
            if wait_time is None:
                raise RateLimitExceededError(
                    f"Превышен лимит запросов для хоста '{request.url.host}'",
                    function="send",
                    limit_key=limit_key,
                    max_calls=self._rate_limit_calls,
                    period=self._rate_limit_period,
                )
            if wait_time > 0.0:
                time.sleep(wait_time)

        # 2. Cache check (GET)
        cache_key = f"web_cache_{request.url}"
        if request.method == "GET" and self._cache_ttl is not None:
            cached_resp = self._cache_backend.get(cache_key)
            if cached_resp is not None:
                return cast(httpx.Response, cached_resp)

        if self._rotate_ua_enabled and self.user_agent_rotator:
            ua = request.headers.get("user-agent")
            if not ua or ua.startswith("python-httpx"):
                request.headers["user-agent"] = self.user_agent_rotator.get()

        # 4. Выполнение с повторами
        retries = self._retries
        delay = self._retry_delay
        backoff = self._retry_backoff

        for attempt in range(retries + 1):
            try:
                resp = super().send(request, *args, **kwargs)
                if resp.status_code >= 500 and self._retry_on_5xx:
                    resp.raise_for_status()

                # Кэшируем успешный ответ
                if (
                        request.method == "GET"
                        and self._cache_ttl is not None
                        and resp.status_code == 200
                ):
                    resp.read()
                    self._cache_backend.set(
                        cache_key, resp, ttl=self._cache_ttl
                    )

                return resp
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == retries:
                    raise

                logger.warning(
                    "Сбой запроса (попытка %d/%d): %s. Ротация прокси и повтор...",
                    attempt + 1,
                    retries + 1,
                    e,
                )
                if self._rotate_proxy_enabled:
                    self.rotate_proxy()

                time.sleep(delay)
                delay *= backoff

        raise RuntimeError("Недостижимый код")


class AsyncWebClient(httpx.AsyncClient):
    """Асинхронный HTTP-клиент с поддержкой ротации User-Agent, прокси-пулов,

    лимитирования частоты и кэширования GET-запросов.
    """

    def __init__(
            self,
            *args: Any,
            user_agent_rotator: UserAgentRotator | None = None,
            proxy_pool: ProxyPool | None = None,
            rotate_ua: bool = True,
            rotate_proxy: bool = True,
            retries: int = 0,
            retry_delay: float = 1.0,
            retry_backoff: float = 2.0,
            retry_on_5xx: bool = True,
            rate_limit_calls: int | None = None,
            rate_limit_period: float = 1.0,
            rate_limit_strategy: str = "token_bucket",
            rate_limit_wait: bool = False,
            cache_ttl: int | None = None,
            cache_backend: Any | None = None,
            **kwargs: Any,
    ) -> None:
        """Инициализирует AsyncWebClient."""
        self.user_agent_rotator: UserAgentRotator = (
                user_agent_rotator or UserAgentRotator()
        )
        self.proxy_pool: ProxyPool | None = proxy_pool
        self._rotate_ua_enabled: bool = rotate_ua
        self._rotate_proxy_enabled: bool = rotate_proxy

        self._retries: int = retries
        self._retry_delay: float = retry_delay
        self._retry_backoff: float = retry_backoff
        self._retry_on_5xx: bool = retry_on_5xx

        self._rate_limit_calls: int | None = rate_limit_calls
        self._rate_limit_period: float = rate_limit_period
        self._rate_limit_strategy: str = rate_limit_strategy
        self._rate_limit_wait: bool = rate_limit_wait

        self._cache_ttl: int | None = cache_ttl
        self._cache_backend: InMemoryCacheBackend[Any] = (
                cache_backend or InMemoryCacheBackend()
        )

        self._transport_kwargs: dict[str, Any] = {
            "verify": kwargs.get("verify", True),
            "cert": kwargs.get("cert", None),
            "http1": kwargs.get("http1", True),
            "http2": kwargs.get("http2", False),
            "limits": kwargs.get("limits", httpx.Limits()),
            "trust_env": kwargs.get("trust_env", True),
        }

        if self.proxy_pool and "proxy" not in kwargs and "proxies" not in kwargs:
            p = self.proxy_pool.get_next_proxy()
            if p:
                kwargs["proxy"] = p

        super().__init__(*args, **kwargs)

    async def rotate_proxy(self) -> None:
        """Асинхронно переключает текущий клиент на следующий прокси из пула."""
        if not self.proxy_pool:
            return

        p = self.proxy_pool.get_next_proxy()
        if not p:
            return

        # Закрываем старые транспорты асинхронно
        for transport in self._mounts.values():
            if transport is not None:
                await transport.aclose()

        proxy_map = self._get_proxy_map(p, allow_env_proxies=False)
        self._mounts = {
            URLPattern(key): None
            if proxy is None
            else self._init_proxy_transport(proxy, **self._transport_kwargs)
            for key, proxy in proxy_map.items()
        }
        self._mounts = dict(sorted(self._mounts.items()))

    async def send(
            self, request: httpx.Request, *args: Any, **kwargs: Any
    ) -> httpx.Response:
        """Перехватывает отправку запроса для ротации, лимитов и кэширования."""
        # 1. Rate Limit
        if self._rate_limit_calls:
            limit_key = f"web_host_{request.url.host}"
            limiter = get_limiter(
                limit_key,
                self._rate_limit_calls,
                self._rate_limit_period,
                self._rate_limit_strategy,
            )
            wait_time = limiter.acquire(wait=self._rate_limit_wait)
            if wait_time is None:
                raise RateLimitExceededError(
                    f"Превышен лимит запросов для хоста '{request.url.host}'",
                    function="send",
                    limit_key=limit_key,
                    max_calls=self._rate_limit_calls,
                    period=self._rate_limit_period,
                )
            if wait_time > 0.0:
                await asyncio.sleep(wait_time)

        # 2. Cache check (GET)
        cache_key = f"web_cache_{request.url}"
        if request.method == "GET" and self._cache_ttl is not None:
            cached_resp = await self._cache_backend.aget(cache_key)
            if cached_resp is not None:
                return cast(httpx.Response, cached_resp)

        if self._rotate_ua_enabled and self.user_agent_rotator:
            ua = request.headers.get("user-agent")
            if not ua or ua.startswith("python-httpx"):
                request.headers["user-agent"] = self.user_agent_rotator.get()

        # 4. Выполнение с повторами
        retries = self._retries
        delay = self._retry_delay
        backoff = self._retry_backoff

        for attempt in range(retries + 1):
            try:
                resp = await super().send(request, *args, **kwargs)
                if resp.status_code >= 500 and self._retry_on_5xx:
                    resp.raise_for_status()

                # Кэшируем успешный ответ
                if (
                        request.method == "GET"
                        and self._cache_ttl is not None
                        and resp.status_code == 200
                ):
                    await resp.aread()
                    await self._cache_backend.aset(
                        cache_key, resp, ttl=self._cache_ttl
                    )

                return resp
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == retries:
                    raise

                logger.warning(
                    "Сбой асинхронного запроса (попытка %d/%d): %s. Ротация прокси и повтор...",
                    attempt + 1,
                    retries + 1,
                    e,
                )
                if self._rotate_proxy_enabled:
                    await self.rotate_proxy()

                await asyncio.sleep(delay)
                delay *= backoff

        raise RuntimeError("Недостижимый код")
