"""
chutils.http — Лёгковесный HTTP-клиент с батареями.

Предоставляет синхронный и асинхронный HTTP-клиенты с встроенной
поддержкой отказоустойчивости, трассировки и маскирования секретов.

Основное использование:
-----------------------
    from chutils.http import HttpClient, ResiliencePolicy

    policy = ResiliencePolicy(retries=3, timeout=10.0)
    with HttpClient(base_url="https://api.example.com", policy=policy) as client:
        resp = client.get("/users/1")
        resp.raise_for_status()
        data = resp.json()

Stand-alone функции:
-------------------
    from chutils import http
    resp = http.get("https://httpbin.org/get")

Async-использование:
--------------------
    from chutils.http import AsyncHttpClient

    async with AsyncHttpClient(base_url="https://api.example.com") as client:
        resp = await client.get("/status")
"""

from __future__ import annotations

from .api import delete, get, patch, post, put
from .client import AsyncHttpClient, HttpClient
from .fallback import HttpResponse, UrllibFallbackClient
from .resilience import ResiliencePolicy
from .streaming import (
    AsyncEventStreamClient,
    AsyncWebSocketClient,
    EventStreamClient,
    ServerSentEvent,
    WebSocketClient,
)
from .tls_client import (
    CURL_CFFI_AVAILABLE,
    DEFAULT_IMPERSONATE_PROFILE,
    TLSAsyncClient,
    TLSSession,
    create_curl_async_session,
    create_curl_session,
)
from .tracing import create_http_span, inject_trace_headers

__all__ = [
    "CURL_CFFI_AVAILABLE",
    "DEFAULT_IMPERSONATE_PROFILE",
    "AsyncEventStreamClient",
    "AsyncHttpClient",
    "AsyncWebSocketClient",
    "EventStreamClient",
    "HttpClient",
    "HttpResponse",
    "ResiliencePolicy",
    "ServerSentEvent",
    "TLSAsyncClient",
    "TLSSession",
    "UrllibFallbackClient",
    "WebSocketClient",
    "create_curl_async_session",
    "create_curl_session",
    "create_http_span",
    "delete",
    "get",
    "inject_trace_headers",
    "patch",
    "post",
    "put",
]
