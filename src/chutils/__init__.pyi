import datetime
import logging
from abc import ABC
from collections.abc import AsyncIterator, Callable, Iterable, Iterator
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar

from typing_extensions import Self

# Тип для Pydantic моделей
_T = TypeVar("_T")
_F = TypeVar("_F", bound=Callable[..., Any])

# --- init ---
def init(base_dir: str) -> None: ...
def get_config(
    model: type[_T] | None = None,
    remote_url: str | None = None,
    remote_auth: tuple[str, str] | None = None,
    polling_interval: int | None = None,
) -> dict[str, Any] | _T: ...
def get_config_value(
    section: str, key: str, fallback: Any = None, config: dict[str, Any] | None = None
) -> Any: ...
def get_config_int(
    section: str, key: str, fallback: int = 0, config: dict[str, Any] | None = None
) -> int: ...
def get_config_float(
    section: str, key: str, fallback: float = 0.0, config: dict[str, Any] | None = None
) -> float: ...
def get_config_boolean(
    section: str, key: str, fallback: bool = False, config: dict[str, Any] | None = None
) -> bool: ...
def get_config_list(
    section: str,
    key: str,
    fallback: list[Any] | None = None,
    config: dict[str, Any] | None = None,
) -> list[Any]: ...
def get_config_section(
    section_name: str,
    fallback: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    model: type[_T] | None = None,
) -> dict[str, Any] | _T: ...
def get_config_path(
    section: str,
    key: str,
    fallback: str | None = None,
    config: dict[str, Any] | None = None,
    resolve_from_root: bool = True,
) -> str | None: ...
async def aget_config(model: type[_T] | None = None) -> dict[str, Any] | _T: ...
def save_config_value(
    section: str,
    key: str,
    value: Any,
    cfg_file: str | None = None,
    save_to_local: bool = False,
    notify: bool = True,
) -> bool: ...
async def asave_config_value(
    section: str,
    key: str,
    value: Any,
    cfg_file: str | None = None,
    save_to_local: bool = False,
    notify: bool = True,
) -> bool: ...
def start_config_watcher() -> bool: ...
def stop_config_watcher() -> None: ...
def on_config_change(callback: Callable[[], None]) -> None: ...
def generate_yaml_template(model_class: type[_T]) -> str: ...
def generate_env_template(model_class: type[_T], prefix: str = "CH") -> str: ...
def generate_json_schema(model_class: type[_T]) -> str: ...
def get_base_dir() -> str | None: ...
def get_config_file_path() -> str | None: ...
def is_config_loaded() -> bool: ...
def are_paths_initialized() -> bool: ...
def get_config_paths(cfg_file: str | None = None) -> tuple[str | None, str | None]: ...
def get_all_config_paths(
    cfg_file: str | None = None,
) -> tuple[str | None, str | None, str | None]: ...
def export_schema(
    model: type[_T] | str, output_path: str | Any | None = None
) -> str: ...

# --- features ---
def is_feature_enabled(
    feature_name: str, context: dict[str, Any] | None = None
) -> bool: ...
def require_feature(
    feature_name: str, fallback: Callable[..., Any] | None = None
) -> Callable[[_F], _F]: ...

# --- logger ---
class ChutilsLogger(logging.Logger):
    def devdebug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def mediumdebug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def add_mask(self, secret: str) -> None: ...

def setup_logger(
    name: str = "app_logger",
    config_section_name: str | None = None,
    log_level: LogLevel | None = None,
    log_file_name: str | None = None,
    force_reconfigure: bool = False,
    rotation_type: str | None = None,
    max_bytes: int | None = None,
    compress: bool | None = None,
    backup_count: int | None = None,
    encoding: str | None = None,
    when: str | None = None,
    interval: int | None = None,
    utc: bool | None = None,
    at_time: Any = None,
    json_format: bool | None = None,
    use_async: bool | None = None,
    max_queue_size: int | None = None,
) -> ChutilsLogger: ...
def setup_logger_from_config(
    name: str = "app_logger",
    config_section_name: str | None = None,
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
def cli_command(func: _F) -> _F: ...

# --- time ---
def utc_now() -> datetime.datetime: ...
def parse_datetime(value: str | float) -> datetime.datetime: ...
def humanize_timedelta(
    dt: datetime.datetime | datetime.timedelta | float,
    locale: str = "ru",
    custom_locales: dict[str, Any] | None = None,
) -> str: ...

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
    def __init__(
        self,
        service_name: str | None = None,
        prefix: str | None = None,
        auto_mask_logs: bool = True,
        providers: list[Any] | None = None,
    ) -> None: ...
    def get_secret(
        self, key: str, fallback: str | None = None, required: bool = False
    ) -> str | None: ...
    def save_secret(self, key: str, value: str) -> bool: ...
    def delete_secret(self, key: str) -> bool: ...
    def update_secret(self, key: str, value: str) -> bool: ...
    async def aget_secret(
        self, key: str, fallback: str | None = None, required: bool = False
    ) -> str | None: ...
    async def asave_secret(self, key: str, value: str) -> bool: ...
    async def adelete_secret(self, key: str) -> bool: ...

# --- tracing ---
IS_OTEL_AVAILABLE: bool

def trace(
    name: Any | None = None,
    attributes: dict[str, Any] | None = None,
    capture_kwargs: bool = False,
) -> Callable[[_F], _F]: ...
def setup_tracing(
    service_name: str,
    exporter_type: str = "console",
    otlp_endpoint: str | None = None,
    otlp_protocol: str = "grpc",
) -> bool: ...

# --- decorators ---
def log_function_details(func: _F) -> _F: ...
def retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: bool = False,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[_F], _F]: ...
def timeout(seconds: float, fallback: Any = ...) -> Callable[[_F], _F]: ...
def rate_limit(
    max_calls: int,
    period: float,
    strategy: str = "token_bucket",
    wait: bool = False,
    key_func: Callable[..., str] | None = None,
) -> Callable[[_F], _F]: ...
def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[_F], _F]: ...
def semaphore(
    max_concurrent: int, key: Callable[..., Any] | None = None
) -> Callable[[_F], _F]: ...
def bulkhead(
    max_concurrent: int,
    max_waiting: int = 0,
    timeout: float | None = None,
    fallback: Any = ...,
    key: Callable[..., Any] | None = None,
) -> Callable[[_F], _F]: ...

# --- exceptions ---
class ChutilsException(Exception):
    context: dict[str, Any]

    def __init__(self, message: str, **context: Any) -> None: ...

class ChutilsConfigurationError(ChutilsException): ...
class ConfigError(ChutilsException): ...
class ConfigLoadError(ConfigError): ...
class ConfigParseError(ConfigError): ...
class ConfigKeyNotFoundError(ConfigError): ...
class SecretError(ChutilsException): ...
class SecretNotFoundError(SecretError): ...
class SecretProviderError(SecretError): ...
class LoggerConfigurationError(ChutilsException): ...
class WatcherInitializationError(ChutilsException): ...
class OptionalDependencyError(ChutilsException): ...
class ChutilsTimeoutError(ChutilsException): ...
class EventBusError(ChutilsException): ...

class EventBusExceptionGroup(EventBusError):
    exceptions: list[Exception]

    def __init__(
        self, message: str, exceptions: list[Exception], **context: Any
    ) -> None: ...

class RateLimitExceededError(ChutilsException): ...
class CircuitBreakerOpenError(ChutilsException): ...
class BulkheadLimitExceeded(ChutilsException): ...
class DependencyError(ChutilsException): ...
class AuditError(ChutilsException): ...

class AuditIntegrityError(AuditError):
    def __init__(self, message: str, record_id: str, **context: Any) -> None: ...

class DependencyNotFoundError(DependencyError): ...
class DependencyResolutionError(DependencyError): ...

# --- events ---
class ErrorStrategy(str, Enum):
    IGNORE = "ignore"
    FAIL_FAST = "fail_fast"
    COLLECT = "collect"

class EventBus:
    error_strategy: ErrorStrategy

    def __init__(
        self, error_strategy: ErrorStrategy = ErrorStrategy.IGNORE
    ) -> None: ...
    def subscribe(
        self, event_name: str
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
    def unsubscribe(self, event_name: str, func: Callable[..., Any]) -> None: ...
    def publish(
        self,
        event_name: str,
        *args: Any,
        error_strategy: ErrorStrategy | None = None,
        **kwargs: Any,
    ) -> None: ...
    async def publish_async(
        self,
        event_name: str,
        *args: Any,
        error_strategy: ErrorStrategy | None = None,
        **kwargs: Any,
    ) -> None: ...

def subscribe(
    event_name: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
def publish(
    event_name: str,
    *args: Any,
    error_strategy: ErrorStrategy | None = None,
    **kwargs: Any,
) -> None: ...
async def publish_async(
    event_name: str,
    *args: Any,
    error_strategy: ErrorStrategy | None = None,
    **kwargs: Any,
) -> None: ...

# --- tasks ---
def periodic_task(
    interval_seconds: float | Callable[[], int | float] | str,
    run_immediately: bool = False,
    overlap: bool = False,
    error_strategy: Any = ...,
    name: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
def start_scheduler() -> None: ...
async def stop_scheduler() -> None: ...

# --- di ---
class Container:
    def __init__(self) -> None: ...
    def register(
        self,
        dependency_type: type[Any] | str,
        provider: Callable[..., Any] | None = None,
        scope: str = "singleton",
    ) -> None: ...
    def has_provider(self, dependency_type: type[Any] | str) -> bool: ...
    def resolve(self, dependency_type: type[_T] | str | Any) -> _T: ...
    def clear(self) -> None: ...

container: Container
default_container: Container

def provide(
    scope: str = "singleton", container: Container | None = None
) -> Callable[[Any], Any]: ...
def inject(
    func_or_container: Callable[..., Any] | Container | None = None,
    *,
    container: Container | None = None,
) -> Any: ...
def Inject() -> Any: ...

# --- text ---
def natsort_key(s: str) -> list[int | str]: ...
def is_significant_difference(
    text1: str, text2: str, threshold: float = 0.9
) -> bool: ...

# --- crypto ---
def encrypt_portable(data: str, seed: str) -> str: ...
def decrypt_portable(
    encrypted_data: str, seed: str, raise_on_error: bool = ...
) -> str | None: ...
def encrypt_file(
    file_path: str | Path, seed: str, output_path: str | Path | None = None
) -> Path: ...
def decrypt_file(
    file_path: str | Path,
    seed: str,
    output_path: str | Path | None = None,
    raise_on_error: bool = ...,
) -> bool: ...

# --- fs ---
def remove_path(
    path: str | Path,
    *,
    retries: int = 3,
    delay: float = 0.1,
    on_locked: Literal["raise", "rename_orphan", "warn"] = "warn",
    orphan_collision: Literal["raise", "overwrite", "unique"] = "raise",
) -> bool: ...
def cleanup_paths(
    *paths: str | Path,
    retries: int = 3,
    delay: float = 0.1,
    on_locked: Literal["raise", "rename_orphan", "warn"] = "warn",
    orphan_collision: Literal["raise", "overwrite", "unique"] = "raise",
) -> None: ...
def safe_filename(
    name: str,
    replacement: str = "_",
    strip_chars: str = " _.-",
    max_length: int = 255,
    transliterate: bool = False,
) -> str: ...
def zip_folder(
    folder_path: str | Path,
    output_path: str | Path,
    compression: int = ...,
    exclude: list[str] | None = None,
) -> Path: ...

# --- web ---
class WebClient: ...
class AsyncWebClient: ...

# --- scraping ---
class BezierCurveGenerator:
    def generate(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        steps: int = 30,
        deviation: float = 0.2,
    ) -> list[tuple[int, int]]: ...

class WindMouseGenerator:
    def __init__(
        self,
        gravity: float = 9.0,
        wind: float = 3.0,
        min_wait: float = 0.002,
        max_wait: float = 0.005,
        max_step: float = 15.0,
        target_area: float = 8.0,
    ) -> None: ...
    def generate(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        gravity: float | None = None,
        wind: float | None = None,
        min_wait: float | None = None,
        max_wait: float | None = None,
        max_step: float | None = None,
        target_area: float | None = None,
    ) -> list[tuple[int, int, float]]: ...

class JitterDelayGenerator:
    def __init__(self, strategy: str = "lognormal", jitter: float = 0.15) -> None: ...
    def generate(self, base_delay: float) -> float: ...

class KeyboardTypoGenerator:
    def __init__(
        self, layout_error_rate: float = 0.0, delayed_fix_rate: float = 0.0
    ) -> None: ...
    def generate_sequence(
        self,
        text: str,
        error_rate: float = 0.05,
        layout_error_rate: float | None = None,
        delayed_fix_rate: float | None = None,
    ) -> list[Any]: ...

def human_sleep(min_seconds: float, max_seconds: float) -> None: ...
async def async_human_sleep(min_seconds: float, max_seconds: float) -> None: ...
async def async_move_mouse(
    page: Any,
    x: int,
    y: int,
    start: tuple[int, int] | None = None,
    steps: int = 30,
    delay_between_steps: float = 0.01,
    algorithm: str = "bezier",
) -> None: ...
async def async_click(
    page: Any,
    selector: str | None = None,
    x: int | None = None,
    y: int | None = None,
    start: tuple[int, int] | None = None,
    algorithm: str = "windmouse",
    button: str = "left",
) -> None: ...
async def async_scroll_to(
    page: Any,
    x: int,
    y: int,
    selector: str | None = None,
    steps: int = 10,
    delay_between_steps: float = 0.01,
) -> None: ...
async def async_type_text(
    page: Any,
    selector: str,
    text: str,
    error_rate: float = 0.05,
    speed_wpm: float = 40.0,
) -> None: ...
def move_mouse(
    driver: Any,
    x: int,
    y: int,
    start: tuple[int, int] | None = None,
    steps: int = 30,
    delay_between_steps: float = 0.01,
    algorithm: str = "bezier",
) -> None: ...
def click(
    driver: Any,
    selector: str | None = None,
    x: int | None = None,
    y: int | None = None,
    start: tuple[int, int] | None = None,
    algorithm: str = "windmouse",
) -> None: ...
def scroll_to(
    driver: Any,
    x: int,
    y: int,
    selector: str | None = None,
    steps: int = 10,
    delay_between_steps: float = 0.01,
) -> None: ...
def type_text(
    driver: Any,
    selector: str,
    text: str,
    error_rate: float = 0.05,
    speed_wpm: float = 40.0,
) -> None: ...
async def apply_antidetect_playwright(
    context: Any,
    *,
    webgl_vendor: str = ...,
    webgl_renderer: str = ...,
    hardware_concurrency: int = ...,
    device_memory: int = ...,
) -> None: ...
def apply_antidetect_selenium(
    driver: Any,
    *,
    webgl_vendor: str = ...,
    webgl_renderer: str = ...,
    hardware_concurrency: int = ...,
    device_memory: int = ...,
) -> None: ...
async def apply_antidetect_nodriver(
    tab: Any,
    *,
    webgl_vendor: str = ...,
    webgl_renderer: str = ...,
    hardware_concurrency: int = ...,
    device_memory: int = ...,
) -> None: ...
def get_browser_launch_args(*, no_sandbox: bool = ...) -> list[str]: ...

# --- scraping captcha ---
class RuCaptchaSolver:
    def __init__(
        self, api_key: str | None = None, host: str = "https://rucaptcha.com"
    ) -> None: ...
    def solve_image(
        self,
        image_data: bytes | str,
        timeout: float = 60.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...
    def solve_recaptcha(
        self,
        sitekey: str,
        page_url: str,
        timeout: float = 120.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...

class AsyncRuCaptchaSolver:
    def __init__(
        self, api_key: str | None = None, host: str = "https://rucaptcha.com"
    ) -> None: ...
    async def solve_image(
        self,
        image_data: bytes | str,
        timeout: float = 60.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...
    async def solve_recaptcha(
        self,
        sitekey: str,
        page_url: str,
        timeout: float = 120.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...

class AntiCaptchaSolver:
    def __init__(
        self, api_key: str | None = None, host: str = "https://api.anti-captcha.com"
    ) -> None: ...
    def solve_image(
        self,
        image_data: bytes | str,
        timeout: float = 60.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...
    def solve_recaptcha(
        self,
        sitekey: str,
        page_url: str,
        timeout: float = 120.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...

class AsyncAntiCaptchaSolver:
    def __init__(
        self, api_key: str | None = None, host: str = "https://api.anti-captcha.com"
    ) -> None: ...
    async def solve_image(
        self,
        image_data: bytes | str,
        timeout: float = 60.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...
    async def solve_recaptcha(
        self,
        sitekey: str,
        page_url: str,
        timeout: float = 120.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...

class CapMonsterSolver:
    def __init__(
        self, api_key: str | None = None, host: str = "https://api.capmonster.cloud"
    ) -> None: ...
    def solve_image(
        self,
        image_data: bytes | str,
        timeout: float = 60.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...
    def solve_recaptcha(
        self,
        sitekey: str,
        page_url: str,
        timeout: float = 120.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...

class AsyncCapMonsterSolver:
    def __init__(
        self, api_key: str | None = None, host: str = "https://api.capmonster.cloud"
    ) -> None: ...
    async def solve_image(
        self,
        image_data: bytes | str,
        timeout: float = 60.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...
    async def solve_recaptcha(
        self,
        sitekey: str,
        page_url: str,
        timeout: float = 120.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str: ...

class CaptchaError(ChutilsException): ...
class CaptchaTimeoutError(CaptchaError): ...
class CaptchaBalanceError(CaptchaError): ...
class CaptchaServiceError(CaptchaError): ...

# --- Submodules ---
from sqlalchemy import Engine

# --- db ---
from sqlalchemy.orm import Session

from . import audit as audit
from . import config as config
from . import context as context
from . import crypto as crypto
from . import db as db
from . import decorators as decorators
from . import dev as dev
from . import di as di
from . import diagnostics as diagnostics
from . import events as events
from . import exceptions as exceptions
from . import features as features
from . import fs as fs
from . import lifecycle as lifecycle
from . import logger as logger
from . import metrics as metrics
from . import scraping as scraping
from . import secret_manager as secret_manager
from . import tasks as tasks
from . import text as text
from . import time as time
from . import tracing as tracing
from . import validation as validation
from . import web as web
from .diagnostics import DiagnosticsManager as DiagnosticsManager
from .env import BaseEnvManifest as BaseEnvManifest
from .exceptions import ChutilsValidationError as ChutilsValidationError
from .exceptions import EnvValidationError as EnvValidationError
from .validation import validate_call as validate_call
from .validation import validate_data as validate_data

class DatabaseManager:
    def __init__(
        self,
        database_url: str | None = None,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        metadata: Any = None,
    ) -> None: ...
    @property
    def engine(self) -> Engine: ...
    @property
    def base(self) -> Any: ...
    @property
    def session_factory(self) -> Any: ...
    def get_session(self) -> Session: ...
    def run_migrations(self, directory: str | Path | None = None) -> None: ...

# --- audit ---
import contextlib

class AuditEvent:
    id: str
    timestamp: datetime.datetime
    actor: str
    action: str
    target: str | None
    status: str
    details: dict[str, Any]
    env: dict[str, Any]
    prev_hash: str
    hash: str

    def __init__(
        self,
        actor: str,
        action: str,
        target: str | None = None,
        status: str = "success",
        details: dict[str, Any] | None = None,
        prev_hash: str = "",
    ) -> None: ...
    def to_jsonl(self) -> str: ...
    @classmethod
    def from_jsonl(cls, line: str) -> AuditEvent: ...

class BaseAuditBackend:
    def log(
        self,
        action: str,
        actor: str,
        *,
        target: str | None = None,
        status: str = "success",
        details: dict[str, Any] | None = None,
    ) -> str: ...
    def verify_integrity(self) -> bool: ...

class FileBackend(BaseAuditBackend):
    def __init__(self, path: str | Path) -> None: ...

class SqliteBackend(BaseAuditBackend):
    def __init__(self, path: str | Path) -> None: ...

class PostgresBackend(BaseAuditBackend):
    def __init__(self, connection: Any) -> None: ...

class _AuditContextState:
    status: str
    details: dict[str, Any]

def audit_context(
    action: str,
    actor: str,
    *,
    target: str | None = None,
    backend: Any,
) -> contextlib.AbstractContextManager[_AuditContextState]: ...
def audit_event(
    action: str,
    actor: str | Callable[..., str] = "system",
    *,
    target: str | Callable[..., str] | None = None,
    backend: Any,
) -> Callable[[_F], _F]: ...

# --- http ---

class HttpResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes
    elapsed: float
    url: str

    @property
    def text(self) -> str: ...
    def json(self) -> Any: ...
    def raise_for_status(self) -> None: ...

class ResiliencePolicy:
    retries: int
    retry_delay: float
    retry_backoff: float
    retry_jitter: bool
    timeout: float | None
    max_concurrency: int | None
    cb_failure_threshold: int
    cb_recovery_timeout: float

    def __init__(
        self,
        *,
        retries: int = 3,
        retry_delay: float = 0.5,
        retry_backoff: float = 2.0,
        retry_jitter: bool = False,
        retry_exceptions: tuple[type[Exception], ...] = ...,
        retry_on_status_codes: tuple[int, ...] = ...,
        timeout: float | None = None,
        max_concurrency: int | None = None,
        cb_failure_threshold: int = 5,
        cb_recovery_timeout: float = 30.0,
    ) -> None: ...
    def apply_sync(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any: ...
    async def apply_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any: ...

class HttpClient:
    base_url: str
    timeout: float | None
    policy: ResiliencePolicy | None

    def __init__(
        self,
        *,
        base_url: str = "",
        default_headers: dict[str, str] | None = None,
        timeout: float | None = 30.0,
        policy: ResiliencePolicy | None = None,
        sensitive_headers: set[str] | None = None,
    ) -> None: ...
    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    def get(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    def post(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    def put(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    def patch(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *args: object) -> None: ...

class AsyncHttpClient:
    base_url: str
    timeout: float | None
    policy: ResiliencePolicy | None

    def __init__(
        self,
        *,
        base_url: str = "",
        default_headers: dict[str, str] | None = None,
        timeout: float | None = 30.0,
        policy: ResiliencePolicy | None = None,
        sensitive_headers: set[str] | None = None,
    ) -> None: ...
    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    async def get(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    async def post(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    async def put(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    async def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    async def patch(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    async def aclose(self) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *args: object) -> None: ...

class ServerSentEvent:
    id: str | None
    event: str | None
    data: str
    retry: int | None
    raw: str
    def __init__(
        self,
        id: str | None = None,
        event: str | None = None,
        data: str = "",
        retry: int | None = None,
        raw: str = "",
    ) -> None: ...

class AsyncEventStreamClient:
    url: str
    headers: dict[str, str]
    timeout: float | None
    filter_heartbeats: bool
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        filter_heartbeats: bool = True,
        reconnect_strategy: Iterable[float]
        | Callable[[], Iterable[float]]
        | None = None,
    ) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *args: object) -> None: ...
    def __aiter__(self) -> AsyncIterator[ServerSentEvent]: ...

class EventStreamClient:
    url: str
    headers: dict[str, str]
    timeout: float | None
    filter_heartbeats: bool
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        filter_heartbeats: bool = True,
        reconnect_strategy: Iterable[float]
        | Callable[[], Iterable[float]]
        | None = None,
    ) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *args: object) -> None: ...
    def __iter__(self) -> Iterator[ServerSentEvent]: ...

class AsyncWebSocketClient:
    url: str
    headers: dict[str, str]
    filter_heartbeats: bool
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        filter_heartbeats: bool = True,
        reconnect_strategy: Iterable[float]
        | Callable[[], Iterable[float]]
        | None = None,
    ) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *args: object) -> None: ...
    async def send(self, message: str | bytes) -> None: ...
    async def recv(self) -> str | bytes: ...
    def __aiter__(self) -> AsyncIterator[str | bytes]: ...

class WebSocketClient:
    url: str
    headers: dict[str, str]
    filter_heartbeats: bool
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        filter_heartbeats: bool = True,
        reconnect_strategy: Iterable[float]
        | Callable[[], Iterable[float]]
        | None = None,
    ) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *args: object) -> None: ...
    def send(self, message: str | bytes) -> None: ...
    def recv(self) -> str | bytes: ...
    def __iter__(self) -> Iterator[str | bytes]: ...

class UrllibFallbackClient:
    def __init__(
        self,
        *,
        base_url: str = "",
        default_headers: dict[str, str] | None = None,
        timeout: float | None = 30.0,
        policy: ResiliencePolicy | None = None,
        sensitive_headers: set[str] | None = None,
    ) -> None: ...
    def get(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    def post(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any | None = None,
        data: bytes | str | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *args: object) -> None: ...

class HttpClientError(ChutilsException): ...

def inject_trace_headers(headers: dict[str, str]) -> dict[str, str]: ...
def create_http_span(
    method: str, url: str, tracer_name: str = "chutils.http"
) -> Any: ...

# standalone http functions
def get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    policy: ResiliencePolicy | None = None,
) -> HttpResponse: ...
def post(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_data: Any | None = None,
    data: bytes | str | None = None,
    timeout: float | None = None,
    policy: ResiliencePolicy | None = None,
) -> HttpResponse: ...
def put(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_data: Any | None = None,
    data: bytes | str | None = None,
    timeout: float | None = None,
    policy: ResiliencePolicy | None = None,
) -> HttpResponse: ...
def delete(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    policy: ResiliencePolicy | None = None,
) -> HttpResponse: ...
def patch(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_data: Any | None = None,
    data: bytes | str | None = None,
    timeout: float | None = None,
    policy: ResiliencePolicy | None = None,
) -> HttpResponse: ...

# store
class BaseStoreBackend(ABC):
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any, ttl: float | None = None) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
    def clear(self) -> bool: ...
    async def aget(self, key: str, default: Any = None) -> Any: ...
    async def aset(self, key: str, value: Any, ttl: float | None = None) -> bool: ...
    async def adelete(self, key: str) -> bool: ...
    async def aexists(self, key: str) -> bool: ...
    async def aclear(self) -> bool: ...

class MemoryStore(BaseStoreBackend):
    def __init__(self) -> None: ...

class RedisStore(BaseStoreBackend):
    def __init__(
        self, url: str = "redis://localhost:6379/0", **kwargs: Any
    ) -> None: ...

class MemcachedStore(BaseStoreBackend):
    def __init__(
        self, host: str = "127.0.0.1", port: int = 11211, **kwargs: Any
    ) -> None: ...

class StoreManager:
    def __init__(
        self,
        backend: BaseStoreBackend | None = None,
        serializer: str | Any = "json",
        prefix: str = "",
    ) -> None: ...
    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> StoreManager: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any, ttl: float | None = None) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
    def clear(self) -> bool: ...
    async def aget(self, key: str, default: Any = None) -> Any: ...
    async def aset(self, key: str, value: Any, ttl: float | None = None) -> bool: ...
    async def adelete(self, key: str) -> bool: ...
    async def aexists(self, key: str) -> bool: ...
    async def aclear(self) -> bool: ...

def store_cache(
    store: StoreManager | None = None, ttl: float = 60, key_prefix: str = "cache:"
) -> Callable[..., Any]: ...

# --- scraping & fingerprinting ---
class AntidetectConfig:
    user_agent: str | None
    platform: str
    hardware_concurrency: int
    device_memory: int
    webgl_vendor: str
    webgl_renderer: str
    locale: str
    timezone: str
    screen_width: int | None
    screen_height: int | None
    screen_avail_height: int | None
    device_pixel_ratio: float | None
    apply_webrtc_leak_protection: bool
    apply_audio_fingerprint: bool
    apply_client_hints: bool
    def __init__(self, **kwargs: Any) -> None: ...
    @classmethod
    def from_seed(
        cls, seed: int | str, os_target: str = "windows"
    ) -> AntidetectConfig: ...
    @classmethod
    def from_fingerprint(cls, profile: FingerprintProfile) -> AntidetectConfig: ...
    @classmethod
    def from_browserforge(
        cls,
        seed: int | str | None = None,
        *,
        browser: str = "chrome",
        os: str = "windows",
        stealth_minimal: bool = True,
    ) -> AntidetectConfig: ...
    @classmethod
    def from_procedural(
        cls, seed: int | str | None = None, os_target: str = "windows"
    ) -> AntidetectConfig: ...
    def get_init_script(self) -> str: ...
    def apply_to_playwright_context(self, context: Any) -> None: ...
    async def apply_to_playwright_context_async(self, context: Any) -> None: ...
    def apply_to_selenium_options(self, options: Any) -> None: ...
    async def apply_to_nodriver_tab(self, tab: Any) -> None: ...

class FingerprintProfile:
    seed: int | str | None
    os: str
    browser: str
    user_agent: str
    webgl: Any
    screen: Any
    hardware: Any
    audio: Any
    media_devices: list[Any]
    client_hints: dict[str, Any]
    source: str
    def to_antidetect_config(self) -> AntidetectConfig: ...
    def to_dict(self) -> dict[str, Any]: ...
    def to_json(self, indent: int = 2) -> str: ...
    def save_to_file(self, path: str | Path) -> None: ...
    @classmethod
    def from_file(cls, path: str | Path) -> FingerprintProfile: ...
    async def apply_to_tab(self, tab: Any) -> None: ...
    async def apply_to_page(self, page: Any) -> None: ...

class FingerprintSynthesizer:
    mode: str
    os_target: str
    locale: str
    def __init__(
        self,
        mode: Literal["auto", "procedural", "browserforge", "fpgen"] = "auto",
        os_target: str = "windows",
        locale: str = "ru-RU",
    ) -> None: ...
    def synthesize(self, seed: int | str | None = None) -> FingerprintProfile: ...
    def get_or_create(
        self, seed: int | str, storage_dir: str | Path
    ) -> FingerprintProfile: ...
    @staticmethod
    def is_browserforge_available() -> bool: ...
    @staticmethod
    def is_fpgen_available() -> bool: ...
    @classmethod
    def create_procedural(
        cls,
        seed: int | str | None = None,
        os_target: str = "windows",
        locale: str = "ru-RU",
    ) -> FingerprintProfile: ...
    @classmethod
    def create_from_browserforge(
        cls,
        browser: str = "chrome",
        os_target: str = "windows",
        seed: int | str | None = None,
    ) -> FingerprintProfile: ...
