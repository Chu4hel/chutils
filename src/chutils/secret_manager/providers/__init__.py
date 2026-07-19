from __future__ import annotations

from typing import TYPE_CHECKING

# ruff: noqa: E402

if TYPE_CHECKING:
    from chutils.logger import ChutilsLogger

# Ленивая инициализация логгера модуля
_module_logger = None


def _get_logger() -> ChutilsLogger:
    global _module_logger
    if _module_logger is None:
        from ... import logger as chutils_logger
        _module_logger = chutils_logger.setup_logger("chutils.secret_manager.providers")
    return _module_logger


from .aws import AWSSecretManagerProvider
from .base import SecretProvider
from .dotenv import DotEnvProvider
from .env import EnvProvider
from .gcp import GCPSecretManagerProvider
from .keyring_provider import KeyringProvider

# Expose keyring for mock compatibility in tests
try:
    import keyring  # chutils: ignore[ChutilsIntegrationRule]

    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None  # type: ignore
    KEYRING_AVAILABLE = False

__all__ = [
    "AWSSecretManagerProvider",
    "SecretProvider",
    "KeyringProvider",
    "DotEnvProvider",
    "EnvProvider",
    "KEYRING_AVAILABLE",
    "GCPSecretManagerProvider",
    "keyring",
]
