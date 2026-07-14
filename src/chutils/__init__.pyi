import datetime
import logging
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar, Literal

# Тип для Pydantic моделей
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# --- init ---
def init(base_dir: str) -> None: ...


def get_config(
        model: type[T] | None = None,
        remote_url: str | None = None,
        remote_auth: tuple[str, str] | None = None,
        polling_interval: int | None = None,
) -> dict[str, Any] | T: ...


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
        model: type[T] | None = None,
) -> dict[str, Any] | T: ...


def get_config_path(
        section: str,
        key: str,
        fallback: str | None = None,
        config: dict[str, Any] | None = None,
        resolve_from_root: bool = True,
) -> str | None: ...


async def aget_config(model: type[T] | None = None) -> dict[str, Any] | T: ...


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


def generate_yaml_template(model_class: type[T]) -> str: ...


def generate_env_template(model_class: type[T], prefix: str = "CH") -> str: ...


def generate_json_schema(model_class: type[T]) -> str: ...


def get_base_dir() -> str | None: ...


def get_config_file_path() -> str | None: ...


def is_config_loaded() -> bool: ...


def are_paths_initialized() -> bool: ...


def get_config_paths(cfg_file: str | None = None) -> tuple[str | None, str | None]: ...


def get_all_config_paths(
        cfg_file: str | None = None,
) -> tuple[str | None, str | None, str | None]: ...


def export_schema(
        model: type[T] | str, output_path: str | Any | None = None
) -> str: ...


# --- features ---
def is_feature_enabled(
        feature_name: str, context: dict[str, Any] | None = None
) -> bool: ...


def require_feature(
        feature_name: str, fallback: Callable[..., Any] | None = None
) -> Callable[[F], F]: ...


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
def cli_command(func: F) -> F: ...


# --- time ---
def utc_now() -> datetime.datetime: ...


def parse_datetime(value: str | int | float) -> datetime.datetime: ...


def humanize_timedelta(
        dt: datetime.datetime,
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
) -> Callable[[F], F]: ...


def setup_tracing(
        service_name: str,
        exporter_type: str = "console",
        otlp_endpoint: str | None = None,
        otlp_protocol: str = "grpc",
) -> bool: ...


# --- decorators ---
def log_function_details(func: F) -> F: ...


def retry(
        retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        jitter: bool = False,
        exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]: ...


def timeout(seconds: float, fallback: Any = ...) -> Callable[[F], F]: ...


def rate_limit(
        max_calls: int,
        period: float,
        strategy: str = "token_bucket",
        wait: bool = False,
        key_func: Callable[..., str] | None = None,
) -> Callable[[F], F]: ...


def circuit_breaker(
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]: ...


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
        interval_seconds: int,
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
            dependency_type: type[Any],
            provider: Callable[..., Any] | None = None,
            scope: str = "singleton",
    ) -> None: ...

    def has_provider(self, dependency_type: type[Any]) -> bool: ...

    def resolve(self, dependency_type: type[T]) -> T: ...

    def clear(self) -> None: ...


container: Container


def provide(
        scope: str = "singleton", container: Container | None = None
) -> Callable[[Any], Any]: ...


def inject(
        container: Container | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def Inject() -> Any: ...


# --- text ---
def natsort_key(s: str) -> list[int | str]: ...


def is_significant_difference(
        text1: str, text2: str, threshold: float = 0.9
) -> bool: ...


# --- crypto ---
def encrypt_portable(data: str, seed: str) -> str: ...


def decrypt_portable(encrypted_data: str, seed: str) -> str | None: ...


def encrypt_file(
        file_path: str | Path, seed: str, output_path: str | Path | None = None
) -> Path: ...


def decrypt_file(
        file_path: str | Path, seed: str, output_path: str | Path | None = None
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


class JitterDelayGenerator:
    def __init__(self, strategy: str = "lognormal", jitter: float = 0.15) -> None: ...

    def generate(self, base_delay: float) -> float: ...


class KeyboardTypoGenerator:
    def generate_sequence(self, text: str, error_rate: float = 0.05) -> list[Any]: ...


def human_sleep(min_seconds: float, max_seconds: float) -> None: ...


async def async_human_sleep(min_seconds: float, max_seconds: float) -> None: ...


async def async_move_mouse(
        page: Any,
        x: int,
        y: int,
        start: tuple[int, int] | None = None,
        steps: int = 30,
        delay_between_steps: float = 0.01,
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
        page: Any, selector: str, text: str, error_rate: float = 0.05, speed_wpm: float = 40.0
) -> None: ...


def move_mouse(
        driver: Any,
        x: int,
        y: int,
        start: tuple[int, int] | None = None,
        steps: int = 30,
        delay_between_steps: float = 0.01,
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
        driver: Any, selector: str, text: str, error_rate: float = 0.05, speed_wpm: float = 40.0
) -> None: ...


async def apply_antidetect_playwright(context: Any) -> None: ...


def apply_antidetect_selenium(driver: Any) -> None: ...


def get_browser_launch_args() -> list[str]: ...


# --- scraping captcha ---
class RuCaptchaSolver:
    def __init__(self, api_key: str | None = None, host: str = "https://rucaptcha.com") -> None: ...

    def solve_image(self, image_data: bytes | str, timeout: float = 60.0, poll_interval: float = 5.0,
                    **kwargs: Any) -> str: ...

    def solve_recaptcha(self, sitekey: str, page_url: str, timeout: float = 120.0, poll_interval: float = 5.0,
                        **kwargs: Any) -> str: ...


class AsyncRuCaptchaSolver:
    def __init__(self, api_key: str | None = None, host: str = "https://rucaptcha.com") -> None: ...

    async def solve_image(self, image_data: bytes | str, timeout: float = 60.0, poll_interval: float = 5.0,
                          **kwargs: Any) -> str: ...

    async def solve_recaptcha(self, sitekey: str, page_url: str, timeout: float = 120.0, poll_interval: float = 5.0,
                              **kwargs: Any) -> str: ...


class AntiCaptchaSolver:
    def __init__(self, api_key: str | None = None, host: str = "https://api.anti-captcha.com") -> None: ...

    def solve_image(self, image_data: bytes | str, timeout: float = 60.0, poll_interval: float = 5.0,
                    **kwargs: Any) -> str: ...

    def solve_recaptcha(self, sitekey: str, page_url: str, timeout: float = 120.0, poll_interval: float = 5.0,
                        **kwargs: Any) -> str: ...


class AsyncAntiCaptchaSolver:
    def __init__(self, api_key: str | None = None, host: str = "https://api.anti-captcha.com") -> None: ...

    async def solve_image(self, image_data: bytes | str, timeout: float = 60.0, poll_interval: float = 5.0,
                          **kwargs: Any) -> str: ...

    async def solve_recaptcha(self, sitekey: str, page_url: str, timeout: float = 120.0, poll_interval: float = 5.0,
                              **kwargs: Any) -> str: ...


class CapMonsterSolver:
    def __init__(self, api_key: str | None = None, host: str = "https://api.capmonster.cloud") -> None: ...

    def solve_image(self, image_data: bytes | str, timeout: float = 60.0, poll_interval: float = 5.0,
                    **kwargs: Any) -> str: ...

    def solve_recaptcha(self, sitekey: str, page_url: str, timeout: float = 120.0, poll_interval: float = 5.0,
                        **kwargs: Any) -> str: ...


class AsyncCapMonsterSolver:
    def __init__(self, api_key: str | None = None, host: str = "https://api.capmonster.cloud") -> None: ...

    async def solve_image(self, image_data: bytes | str, timeout: float = 60.0, poll_interval: float = 5.0,
                          **kwargs: Any) -> str: ...

    async def solve_recaptcha(self, sitekey: str, page_url: str, timeout: float = 120.0, poll_interval: float = 5.0,
                              **kwargs: Any) -> str: ...


class CaptchaError(ChutilsException): ...


class CaptchaTimeoutError(CaptchaError): ...


class CaptchaBalanceError(CaptchaError): ...


class CaptchaServiceError(CaptchaError): ...


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
from . import web as web
from . import scraping as scraping
from . import diagnostics as diagnostics
from . import validation as validation

from .diagnostics import DiagnosticsManager as DiagnosticsManager
from .validation import validate_data as validate_data, validate_call as validate_call
from .exceptions import ChutilsValidationError as ChutilsValidationError, EnvValidationError as EnvValidationError
from .env import BaseEnvManifest as BaseEnvManifest
