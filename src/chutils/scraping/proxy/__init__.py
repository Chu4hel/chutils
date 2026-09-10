"""Модуль управления прокси-серверами и аутентификацией."""

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import ProxyConfig as ProxyConfig
    from .parser import parse_proxy as parse_proxy

_LAZY_MAPPING = {
    "ProxyConfig": (".models", "ProxyConfig"),
    "parse_proxy": (".parser", "parse_proxy"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_MAPPING:
        mod_path, attr_name = _LAZY_MAPPING[name]
        module = importlib.import_module(mod_path, __name__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(_LAZY_MAPPING.keys()) + ["__all__", "__doc__"])


__all__ = ["ProxyConfig", "parse_proxy"]
