import importlib.util

from chutils.exceptions import OptionalDependencyError

_HAS_HTTPX = importlib.util.find_spec("httpx") is not None

if not _HAS_HTTPX:
    raise OptionalDependencyError(
        "Модуль 'chutils.web' требует установленной библиотеки 'httpx'.\n"
        "Установите её с помощью команды: pip install chutils[web]",
        dependency="httpx",
        hint="Выполните pip install chutils[web] или pip install httpx."
    )

from .client import WebClient, AsyncWebClient  # noqa: E402

__all__ = ["WebClient", "AsyncWebClient"]
