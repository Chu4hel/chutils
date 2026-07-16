from .models import CheckResult, HealthReport

__all__ = [
    "CheckResult",
    "HealthReport",
    "DiagnosticsManager",
    "get_fastapi_health_handler",
    "get_flask_health_handler",
]

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "DiagnosticsManager":
        from .manager import DiagnosticsManager
        return DiagnosticsManager
    elif name == "get_fastapi_health_handler":
        from .web import get_fastapi_health_handler
        return get_fastapi_health_handler
    elif name == "get_flask_health_handler":
        from .web import get_flask_health_handler
        return get_flask_health_handler
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
