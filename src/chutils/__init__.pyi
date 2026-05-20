import logging
from datetime import datetime
from logging import Handler
from typing import Any, Optional, List, Dict, Type, TypeVar, Union, Tuple, Callable

# Тип для Pydantic моделей
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# --- init ---
def init(base_dir: str) -> None: ...


# --- config ---
def get_config(model: Optional[Type[T]] = None) -> Union[Dict[str, Any], T]: ...


def get_config_value(section: str, key: str, fallback: Any = None, config: Optional[Dict[str, Any]] = None) -> Any: ...


def get_config_int(section: str, key: str, fallback: int = 0, config: Optional[Dict[str, Any]] = None) -> int: ...


def get_config_float(section: str, key: str, fallback: float = 0.0,
                     config: Optional[Dict[str, Any]] = None) -> float: ...


def get_config_boolean(section: str, key: str, fallback: bool = False,
                       config: Optional[Dict[str, Any]] = None) -> bool: ...


def get_config_list(section: str, key: str, fallback: Optional[List[Any]] = None,
                    config: Optional[Dict[str, Any]] = None) -> List[Any]: ...


def get_config_section(section_name: str, fallback: Optional[Dict[str, Any]] = None,
                       config: Optional[Dict[str, Any]] = None, model: Optional[Type[T]] = None) -> Union[
    Dict[str, Any], T]: ...


def get_config_path(section: str, key: str, fallback: Optional[str] = None, config: Optional[Dict[str, Any]] = None,
                    resolve_from_root: bool = True) -> Optional[str]: ...


async def aget_config(model: Optional[Type[T]] = None) -> Union[Dict[str, Any], T]: ...


def save_config_value(section: str, key: str, value: Any, cfg_file: Optional[str] = None, save_to_local: bool = False,
                      notify: bool = True) -> bool: ...


async def asave_config_value(section: str, key: str, value: Any, cfg_file: Optional[str] = None,
                             save_to_local: bool = False, notify: bool = True) -> bool: ...


def start_config_watcher() -> bool: ...


def stop_config_watcher() -> None: ...


def on_config_change(callback: Callable[[], None]) -> None: ...


def generate_yaml_template(model_class: Type[T]) -> str: ...


def generate_env_template(model_class: Type[T], prefix: str = "CH") -> str: ...


def generate_json_schema(model_class: Type[T]) -> str: ...


# --- features ---
def is_feature_enabled(feature_name: str, context: Optional[Dict[str, Any]] = None) -> bool: ...


def require_feature(feature_name: str, fallback: Optional[Callable[..., Any]] = None) -> Callable[[F], F]: ...


# --- logger ---
class ChutilsLogger(logging.Logger):
    def devdebug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def mediumdebug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def add_mask(self, secret: str) -> None: ...


def setup_logger(name: Optional[str] = None, level: Optional[Union[str, int]] = None,
                 log_file: Optional[str] = None) -> ChutilsLogger: ...


class SafeTimedRotatingFileHandler(Handler): ...


# --- context ---
def bind_context(**kwargs: Any) -> None: ...


def unbind_context(*args: str) -> None: ...


def clear_context() -> None: ...


# --- lifecycle ---
def register_cleanup(func: Callable[..., Any]) -> Callable[..., Any]: ...


def setup_graceful_shutdown() -> None: ...


# --- time ---
def utc_now() -> datetime: ...


def parse_datetime(value: Union[str, int, float]) -> datetime: ...


def humanize_timedelta(dt: datetime, locale: str = 'ru', custom_locales: Optional[dict] = None) -> str: ...


# --- secret_manager ---
class SecretManager:
    def __init__(self, service_name: Optional[str] = None, prefix: Optional[str] = None, auto_mask_logs: bool = True,
                 providers: Optional[List[Any]] = None) -> None: ...

    def get_secret(self, key: str) -> Optional[str]: ...

    def save_secret(self, key: str, value: str) -> bool: ...

    def delete_secret(self, key: str) -> bool: ...

    def update_secret(self, key: str, value: str) -> bool: ...

    async def aget_secret(self, key: str) -> Optional[str]: ...

    async def asave_secret(self, key: str, value: str) -> bool: ...

    async def adelete_secret(self, key: str) -> bool: ...


# --- decorators ---
def log_function_details(func: F) -> F: ...


def retry(retries: int = 3, delay: float = 1.0, backoff: float = 2.0, jitter: bool = False,
          exceptions: Tuple[Type[Exception], ...] = (Exception,)) -> Callable[[F], F]: ...


def timeout(seconds: float, fallback: Any = ...) -> Callable[[F], F]: ...


# --- exceptions ---
class ChutilsException(Exception):
    context: Dict[str, Any]

    def __init__(self, message: str, **context: Any) -> None: ...


class ConfigError(ChutilsException): ...


class ConfigLoadError(ConfigError): ...


class ConfigParseError(ConfigError): ...


class SecretError(ChutilsException): ...


class SecretNotFoundError(SecretError): ...


class SecretProviderError(SecretError): ...


class LoggerConfigurationError(ChutilsException): ...


class WatcherInitializationError(ChutilsException): ...


class OptionalDependencyError(ChutilsException): ...


class ChutilsTimeoutError(ChutilsException): ...


# --- Submodules ---
from . import config as config
from . import logger as logger
from . import secret_manager as secret_manager
from . import decorators as decorators
from . import exceptions as exceptions
from . import context as context
from . import lifecycle as lifecycle
from . import features as features
from . import time as time
