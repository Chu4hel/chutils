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

Standalone-функции:
-------------------
    from chutils import http
    resp = http.get("https://httpbin.org/get")
"""
from __future__ import annotations

from .fallback import HttpResponse, UrllibFallbackClient
from .resilience import ResiliencePolicy

__all__ = [
    "HttpResponse",
    "ResiliencePolicy",
    "UrllibFallbackClient",
]
