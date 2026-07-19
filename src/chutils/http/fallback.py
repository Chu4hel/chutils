"""
Fallback HTTP-клиент на базе стандартной библиотеки urllib.request.

Используется когда httpx не установлен. Поддерживает:
- GET, POST, PUT, DELETE, PATCH запросы
- Кастомные заголовки
- Таймауты
- Передачу тела запроса (JSON / bytes / str)
- Базовую обработку ошибок (HTTP-статус-коды)
- Интеграцию с ResiliencePolicy
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .resilience import ResiliencePolicy

_log = logging.getLogger(__name__)

# ─── Сенситивные заголовки для маскирования в логах ─────────────────────────

_SENSITIVE_HEADERS: frozenset[str] = frozenset({
    "authorization",
    "x-api-key",
    "api-key",
    "cookie",
    "set-cookie",
    "token",
    "x-auth-token",
    "proxy-authorization",
})


def _mask_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Маскирует значения чувствительных заголовков для логирования.

    Args:
        headers: Словарь HTTP-заголовков.

    Returns:
        Копия словаря с заменёнными значениями для сенситивных ключей.
    """
    return {
        k: "[MASKED]" if k.lower() in _SENSITIVE_HEADERS else v
        for k, v in headers.items()
    }


# ─── HttpResponse ─────────────────────────────────────────────────────────────


@dataclass
class HttpResponse:
    """Ответ HTTP-запроса.

    Attributes:
        status_code: HTTP-статус-код ответа.
        headers: Заголовки ответа.
        content: Тело ответа в байтах.
        elapsed: Время выполнения запроса в секундах.
        url: Итоговый URL (с учётом редиректов).
    """

    status_code: int
    headers: dict[str, str]
    content: bytes
    elapsed: float
    url: str

    @property
    def text(self) -> str:
        """Тело ответа в виде строки UTF-8.

        Returns:
            Декодированное тело ответа.
        """
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> object:
        """Десериализует тело ответа как JSON.

        Returns:
            Распарсенный JSON-объект.

        Raises:
            ValueError: Если тело не является корректным JSON.
        """
        return json.loads(self.content)

    def raise_for_status(self) -> None:
        """Вызывает исключение, если статус-код указывает на ошибку (4xx / 5xx).

        Raises:
            HttpClientError: Если статус-код >= 400.
        """
        from chutils.exceptions import HttpClientError

        if self.status_code >= 400:
            raise HttpClientError(
                f"HTTP {self.status_code} для URL: {self.url}",
                status_code=self.status_code,
                url=self.url,
            )


# ─── UrllibFallbackClient ─────────────────────────────────────────────────────


class UrllibFallbackClient:
    """Синхронный HTTP-клиент на базе urllib.request.

    Используется как fallback, когда httpx не доступен. Поддерживает
    интеграцию с `ResiliencePolicy` для retry, timeout и semaphore.

    Args:
        base_url: Базовый URL, который будет префиксом для всех запросов.
        default_headers: Заголовки по умолчанию для всех запросов.
        timeout: Таймаут подключения и чтения в секундах.
        policy: Политика отказоустойчивости.
        sensitive_headers: Дополнительные заголовки для маскирования в логах.

    Example:
        ```python
        client = UrllibFallbackClient(
            base_url="https://api.example.com",
            default_headers={"Authorization": "Bearer token"},
            timeout=10.0,
        )
        response = client.get("/users/1")
        response.raise_for_status()
        data = response.json()
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
        """Инициализирует fallback HTTP-клиент.

        Args:
            base_url: Базовый URL для всех запросов.
            default_headers: Заголовки, добавляемые к каждому запросу.
            timeout: Таймаут в секундах (подключение + чтение).
            policy: Политика отказоустойчивости (retry, semaphore и т.д.).
            sensitive_headers: Дополнительные имена заголовков для маскирования.
        """
        self.base_url = base_url.rstrip("/")
        self.default_headers: dict[str, str] = default_headers or {}
        self.timeout = timeout
        self.policy = policy
        self._extra_sensitive: frozenset[str] = frozenset(
            h.lower() for h in (sensitive_headers or set())
        )

    def _is_sensitive(self, header_name: str) -> bool:
        """Проверяет, является ли заголовок чувствительным.

        Args:
            header_name: Имя заголовка.

        Returns:
            True, если заголовок должен быть замаскирован в логах.
        """
        lower = header_name.lower()
        return lower in _SENSITIVE_HEADERS or lower in self._extra_sensitive

    def _mask(self, headers: dict[str, str]) -> dict[str, str]:
        """Маскирует чувствительные заголовки для логирования.

        Args:
            headers: Исходный словарь заголовков.

        Returns:
            Копия словаря с заменёнными значениями.
        """
        return {
            k: "[MASKED]" if self._is_sensitive(k) else v
            for k, v in headers.items()
        }

    def _build_url(self, path: str) -> str:
        """Строит полный URL из base_url и пути.

        Args:
            path: Путь запроса (может быть абсолютным URL).

        Returns:
            Полный URL.
        """
        if path.startswith(("http://", "https://")):
            return path
        return self.base_url + "/" + path.lstrip("/") if self.base_url else path

    def _do_request(
            self,
            method: str,
            url: str,
            headers: dict[str, str],
            body: bytes | None,
            timeout: float | None,
    ) -> HttpResponse:
        """Выполняет HTTP-запрос через urllib.

        Args:
            method: HTTP-метод (GET, POST и т.д.).
            url: Полный URL.
            headers: Заголовки запроса.
            body: Тело запроса в байтах или None.
            timeout: Таймаут в секундах.

        Returns:
            Объект HttpResponse.

        Raises:
            HttpClientError: При сетевой ошибке или HTTP-ошибке 4xx/5xx.
        """
        from chutils.exceptions import HttpClientError

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                content = resp.read()
                elapsed = time.monotonic() - start
                resp_headers = dict(resp.headers.items())
                return HttpResponse(
                    status_code=resp.status,
                    headers=resp_headers,
                    content=content,
                    elapsed=elapsed,
                    url=resp.url,
                )
        except urllib.error.HTTPError as e:
            elapsed = time.monotonic() - start
            content = e.read() if e.fp else b""
            resp_headers = dict(e.headers.items()) if e.headers else {}
            return HttpResponse(
                status_code=e.code,
                headers=resp_headers,
                content=content,
                elapsed=elapsed,
                url=url,
            )
        except urllib.error.URLError as e:
            raise HttpClientError(
                f"Сетевая ошибка при запросе {method} {url}: {e.reason}",
                url=url,
                method=method,
            ) from e

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
        """Выполняет HTTP-запрос с заданным методом.

        Args:
            method: HTTP-метод (GET, POST, PUT, DELETE, PATCH).
            path: Путь или абсолютный URL.
            headers: Дополнительные заголовки запроса.
            json_data: Данные для сериализации в JSON-тело запроса.
            data: Сырое тело запроса (bytes или str).
            timeout: Таймаут для этого конкретного запроса.

        Returns:
            Объект HttpResponse.

        Raises:
            HttpClientError: При сетевой ошибке.
            ValueError: Если переданы одновременно json_data и data.
        """
        if json_data is not None and data is not None:
            raise ValueError("Нельзя передавать json_data и data одновременно.")

        url = self._build_url(path)
        effective_timeout = timeout if timeout is not None else self.timeout

        merged_headers: dict[str, str] = {**self.default_headers, **(headers or {})}

        body: bytes | None = None
        if json_data is not None:
            body = json.dumps(json_data).encode("utf-8")
            merged_headers.setdefault("Content-Type", "application/json")
        elif data is not None:
            body = data.encode("utf-8") if isinstance(data, str) else data

        _log.debug(
            "→ %s %s  headers=%s",
            method.upper(),
            url,
            self._mask(merged_headers),
        )

        def _call() -> HttpResponse:
            return self._do_request(
                method.upper(), url, merged_headers, body, effective_timeout
            )

        if self.policy is not None:
            resp = self.policy.apply_sync(_call)
        else:
            resp = _call()

        assert isinstance(resp, HttpResponse)  # noqa: S101

        _log.debug(
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
            json_data: Данные для JSON-тела запроса.
            data: Сырое тело запроса.
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
            json_data: Данные для JSON-тела запроса.
            data: Сырое тело запроса.
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
            json_data: Данные для JSON-тела запроса.
            data: Сырое тело запроса.
            timeout: Таймаут запроса.

        Returns:
            Объект HttpResponse.
        """
        return self.request("PATCH", path, headers=headers, json_data=json_data, data=data, timeout=timeout)

    def close(self) -> None:
        """Закрывает клиент (no-op для urllib-клиента, для совместимости API)."""

    def __enter__(self) -> UrllibFallbackClient:
        """Поддержка контекстного менеджера.

        Returns:
            Сам экземпляр клиента.
        """
        return self

    def __exit__(self, *args: object) -> None:
        """Закрывает клиент при выходе из контекстного менеджера."""
        self.close()
