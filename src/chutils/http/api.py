"""
Модуль chutils.http.api — Standalone HTTP API-функции.

Предоставляет удобные функции верхнего уровня для выполнения HTTP-запросов
без явного создания экземпляра клиента. Под капотом каждый вызов создаёт
временный `HttpClient` и выполняет запрос.

Использование:
--------------
    from chutils import http

    resp = http.get("https://api.example.com/users/1")
    resp.raise_for_status()

    resp = http.post(
        "https://api.example.com/items",
        json_data={"name": "new item"},
        headers={"Authorization": "Bearer token"},
    )
"""
from __future__ import annotations

from .client import HttpClient
from .fallback import HttpResponse

if False:  # TYPE_CHECKING
    from .resilience import ResiliencePolicy


def get(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        policy: "ResiliencePolicy" | None = None,
) -> HttpResponse:
    """Выполняет GET-запрос.

    Создаёт временный `HttpClient`, выполняет запрос и возвращает ответ.

    Args:
        url: Абсолютный URL запроса.
        headers: Дополнительные HTTP-заголовки.
        timeout: Таймаут запроса в секундах.
        policy: Политика отказоустойчивости (retry, timeout, semaphore).

    Returns:
        Объект HttpResponse с телом, заголовками и статус-кодом ответа.

    Example:
        ```python
        from chutils import http

        resp = http.get("https://httpbin.org/get", timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        ```
    """
    with HttpClient(policy=policy) as client:
        return client.get(url, headers=headers, timeout=timeout)


def post(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: object | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
        policy: "ResiliencePolicy" | None = None,
) -> HttpResponse:
    """Выполняет POST-запрос.

    Args:
        url: Абсолютный URL запроса.
        headers: Дополнительные HTTP-заголовки.
        json_data: Данные для сериализации в JSON-тело запроса.
        data: Сырое тело запроса (bytes или str).
        timeout: Таймаут запроса в секундах.
        policy: Политика отказоустойчивости.

    Returns:
        Объект HttpResponse.

    Example:
        ```python
        resp = http.post(
            "https://api.example.com/users",
            json_data={"name": "Alice", "email": "alice@example.com"},
        )
        resp.raise_for_status()
        ```
    """
    with HttpClient(policy=policy) as client:
        return client.post(url, headers=headers, json_data=json_data, data=data, timeout=timeout)


def put(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: object | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
        policy: "ResiliencePolicy" | None = None,
) -> HttpResponse:
    """Выполняет PUT-запрос.

    Args:
        url: Абсолютный URL запроса.
        headers: Дополнительные HTTP-заголовки.
        json_data: Данные для JSON-тела запроса.
        data: Сырое тело запроса.
        timeout: Таймаут запроса в секундах.
        policy: Политика отказоустойчивости.

    Returns:
        Объект HttpResponse.
    """
    with HttpClient(policy=policy) as client:
        return client.put(url, headers=headers, json_data=json_data, data=data, timeout=timeout)


def delete(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        policy: "ResiliencePolicy" | None = None,
) -> HttpResponse:
    """Выполняет DELETE-запрос.

    Args:
        url: Абсолютный URL запроса.
        headers: Дополнительные HTTP-заголовки.
        timeout: Таймаут запроса в секундах.
        policy: Политика отказоустойчивости.

    Returns:
        Объект HttpResponse.
    """
    with HttpClient(policy=policy) as client:
        return client.delete(url, headers=headers, timeout=timeout)


def patch(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: object | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
        policy: "ResiliencePolicy" | None = None,
) -> HttpResponse:
    """Выполняет PATCH-запрос.

    Args:
        url: Абсолютный URL запроса.
        headers: Дополнительные HTTP-заголовки.
        json_data: Данные для JSON-тела запроса.
        data: Сырое тело запроса.
        timeout: Таймаут запроса в секундах.
        policy: Политика отказоустойчивости.

    Returns:
        Объект HttpResponse.
    """
    with HttpClient(policy=policy) as client:
        return client.patch(url, headers=headers, json_data=json_data, data=data, timeout=timeout)
