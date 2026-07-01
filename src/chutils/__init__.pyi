import datetime
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict, Type, TypeVar, Union, Tuple, Callable, Literal

# Тип для Pydantic моделей
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# --- init ---
def init(base_dir: str) -> None: ...


def get_config(
        model: Optional[Type[T]] = None,
        remote_url: Optional[str] = None,
        remote_auth: Optional[Tuple[str, str]] = None,
        polling_interval: Optional[int] = None,
) -> Union[Dict[str, Any], T]: ...


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


def get_base_dir() -> Optional[str]: ...


def get_config_file_path() -> Optional[str]: ...


def is_config_loaded() -> bool: ...


def are_paths_initialized() -> bool: ...


def get_config_paths(cfg_file: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]: ...


def get_all_config_paths(cfg_file: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[str]]: ...


def export_schema(model: Union[Type[T], str], output_path: Optional[Union[str, Any]] = None) -> str: ...


# --- features ---
def is_feature_enabled(feature_name: str, context: Optional[Dict[str, Any]] = None) -> bool: ...


def require_feature(feature_name: str, fallback: Optional[Callable[..., Any]] = None) -> Callable[[F], F]: ...


# --- logger ---
class ChutilsLogger(logging.Logger):
    def devdebug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def mediumdebug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def add_mask(self, secret: str) -> None: ...


def setup_logger(
        name: str = 'app_logger',
        config_section_name: Optional[str] = None,
        log_level: Optional[LogLevel] = None,
        log_file_name: Optional[str] = None,
        force_reconfigure: bool = False,
        rotation_type: Optional[str] = None,
        max_bytes: Optional[int] = None,
        compress: Optional[bool] = None,
        backup_count: Optional[int] = None,
        encoding: Optional[str] = None,
        when: Optional[str] = None,
        interval: Optional[int] = None,
        utc: Optional[bool] = None,
        at_time: Any = None,
        json_format: Optional[bool] = None,
        use_async: Optional[bool] = None,
        max_queue_size: Optional[int] = None,
) -> ChutilsLogger: ...


def setup_logger_from_config(
        name: str = 'app_logger',
        config_section_name: Optional[str] = None,
        force_reconfigure: bool = False,
) -> ChutilsLogger: ...


class LogLevel(str, Enum):
    DEVDEBUG = "DEVDEBUG"
    DEBUG = "DEBUG"
    MEDIUMDEBUG = "MEDIUMDEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def get_console(stderr: bool = False) -> Any: ...


class SecretMaskingFilter(logging.Filter): ...


class ChutilsJsonFormatter(logging.Formatter): ...


class SafeTimedRotatingFileHandler(logging.Handler): ...


class CompressingRotatingFileHandler(logging.Handler): ...


class CompressingTimedRotatingFileHandler(logging.Handler): ...


DEVDEBUG_LEVEL_NUM: int
MEDIUMDEBUG_LEVEL_NUM: int


# --- context ---
def bind_context(**kwargs: Any) -> Any: ...


def unbind_context(token: Any) -> None: ...


def clear_context() -> None: ...


# --- lifecycle ---
def register_cleanup(func: Callable[..., Any]) -> Callable[..., Any]: ...


def setup_graceful_shutdown() -> None: ...


# --- cli_booster ---
def cli_command(func: F) -> F: ...


# --- time ---
def utc_now() -> datetime.datetime: ...


def parse_datetime(value: Union[str, int, float]) -> datetime.datetime: ...


def humanize_timedelta(dt: datetime.datetime, locale: str = 'ru',
                       custom_locales: Optional[Dict[str, Any]] = None) -> str: ...


# --- env (Discovery) ---
def is_rich_enabled() -> bool: ...


def is_otel_enabled() -> bool: ...


RICH_AVAILABLE: bool
PYDANTIC_AVAILABLE: bool
WATCHDOG_AVAILABLE: bool
JSON_LOGGER_AVAILABLE: bool
OTEL_AVAILABLE: bool


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


# --- tracing ---
IS_OTEL_AVAILABLE: bool


def trace(
        name: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None,
        capture_kwargs: bool = False,
) -> Callable[[F], F]: ...


def setup_tracing(
        service_name: str,
        exporter_type: str = "console",
        otlp_endpoint: Optional[str] = None,
        otlp_protocol: str = "grpc",
) -> bool: ...


# --- decorators ---
def log_function_details(func: F) -> F: ...


def retry(retries: int = 3, delay: float = 1.0, backoff: float = 2.0, jitter: bool = False,
          exceptions: Tuple[Type[Exception], ...] = (Exception,)) -> Callable[[F], F]: ...


def timeout(seconds: float, fallback: Any = ...) -> Callable[[F], F]: ...


def rate_limit(max_calls: int, period: float, strategy: str = "token_bucket", wait: bool = False,
               key_func: Optional[Callable[..., str]] = None) -> Callable[[F], F]: ...


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


class EventBusError(ChutilsException): ...


class EventBusExceptionGroup(EventBusError):
    exceptions: List[Exception]

    def __init__(self, message: str, exceptions: List[Exception], **context: Any) -> None: ...


class RateLimitExceededError(ChutilsException): ...


class DependencyError(ChutilsException): ...


class DependencyNotFoundError(DependencyError): ...


class DependencyResolutionError(DependencyError): ...


# --- events ---
class ErrorStrategy(str, Enum):
    IGNORE = "ignore"
    FAIL_FAST = "fail_fast"
    COLLECT = "collect"


class EventBus:
    error_strategy: ErrorStrategy

    def __init__(self, error_strategy: ErrorStrategy = ErrorStrategy.IGNORE) -> None: ...

    def subscribe(self, event_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

    def unsubscribe(self, event_name: str, func: Callable[..., Any]) -> None: ...

    def publish(self, event_name: str, *args: Any, error_strategy: Optional[ErrorStrategy] = None,
                **kwargs: Any) -> None: ...

    async def publish_async(self, event_name: str, *args: Any, error_strategy: Optional[ErrorStrategy] = None,
                            **kwargs: Any) -> None: ...


def subscribe(event_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def publish(event_name: str, *args: Any, error_strategy: Optional[ErrorStrategy] = None, **kwargs: Any) -> None: ...


async def publish_async(event_name: str, *args: Any, error_strategy: Optional[ErrorStrategy] = None,
                        **kwargs: Any) -> None: ...


# --- tasks ---
def periodic_task(
        interval_seconds: int,
        run_immediately: bool = False,
        overlap: bool = False,
        error_strategy: Any = ...,
        name: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def start_scheduler() -> None: ...


async def stop_scheduler() -> None: ...


# --- di ---
class Container:
    def __init__(self) -> None: ...

    def register(self, dependency_type: Type[Any], provider: Optional[Callable[..., Any]] = None,
                 scope: str = "singleton") -> None: ...

    def has_provider(self, dependency_type: Type[Any]) -> bool: ...

    def resolve(self, dependency_type: Type[T]) -> T: ...

    def clear(self) -> None: ...


container: Container


def provide(scope: str = "singleton", container: Optional[Container] = None) -> Callable[[Any], Any]: ...


def inject(container: Optional[Container] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def Inject() -> Any: ...


# --- text ---
def natsort_key(s: str) -> List[Union[int, str]]: ...


def is_significant_difference(text1: str, text2: str, threshold: float = 0.9) -> bool: ...


# --- crypto ---
def encrypt_portable(data: str, seed: str) -> str: ...


def decrypt_portable(encrypted_data: str, seed: str) -> Optional[str]: ...


def encrypt_file(file_path: Union[str, Path], seed: str, output_path: Optional[Union[str, Path]] = None) -> Path: ...


def decrypt_file(file_path: Union[str, Path], seed: str, output_path: Optional[Union[str, Path]] = None) -> bool: ...


# --- fs ---
def remove_path(
        path: Union[str, Path],
        *,
        retries: int = 3,
        delay: float = 0.1,
        on_locked: Literal["raise", "rename_orphan", "warn"] = "warn",
        orphan_collision: Literal["raise", "overwrite", "unique"] = "raise"
) -> bool: ...


def cleanup_paths(
        *paths: Union[str, Path],
        retries: int = 3,
        delay: float = 0.1,
        on_locked: Literal["raise", "rename_orphan", "warn"] = "warn",
        orphan_collision: Literal["raise", "overwrite", "unique"] = "raise"
) -> None: ...


def safe_filename(
        name: str,
        replacement: str = "_",
        strip_chars: str = " _.-",
        max_length: int = 255,
        transliterate: bool = False
) -> str: ...


def zip_folder(
        folder_path: Union[str, Path],
        output_path: Union[str, Path],
        compression: int = ...,
        exclude: Optional[list[str]] = None
) -> Path: ...


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
from . import tracing as tracing
from . import dev as dev
from . import events as events
from . import tasks as tasks
from . import di as di
from . import metrics as metrics
from . import text as text
from . import crypto as crypto
from . import fs as fs
