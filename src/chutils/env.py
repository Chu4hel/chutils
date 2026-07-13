import importlib.util
import os


# --- Проверка доступности внешних библиотек (Discovery) ---

def _is_installed(package_name: str) -> bool:
    """Проверяет наличие пакета в системе без его импорта."""
    try:
        return importlib.util.find_spec(package_name) is not None
    except (ImportError, ModuleNotFoundError):
        return False


RICH_AVAILABLE = _is_installed("rich")
PYDANTIC_AVAILABLE = _is_installed("pydantic")
WATCHDOG_AVAILABLE = _is_installed("watchdog")
JSON_LOGGER_AVAILABLE = _is_installed("pythonjsonlogger")
OTEL_AVAILABLE = _is_installed("opentelemetry.trace")


def has_pydantic() -> bool:
    """Возвращает True, если Pydantic установлен.

    Returns:
        True, если пакет pydantic доступен для импорта.
    """
    return PYDANTIC_AVAILABLE


def has_rich() -> bool:
    """Возвращает True, если Rich установлен.

    Returns:
        True, если пакет rich доступен для импорта.
    """
    return RICH_AVAILABLE


def has_watchdog() -> bool:
    """Возвращает True, если Watchdog установлен.

    Returns:
        True, если пакет watchdog доступен для импорта.
    """
    return WATCHDOG_AVAILABLE


def is_rich_enabled() -> bool:
    """Централизованная проверка: доступен ли Rich и разрешен ли он настройками.
    
    Учитывает:
    - Наличие установленного пакета rich.
    - Переменные окружения NO_COLOR, CH_NO_COLOR.
    - Специальную переменную CH_NO_RICH (для тестов и headless).

    Returns:
        True, если вывод Rich разрешен и пакет установлен, иначе False.
    """
    if not RICH_AVAILABLE:
        return False

    no_color = os.getenv("NO_COLOR", "").lower() in ["true", "1", "yes", "y"]
    ch_no_color = os.getenv("CH_NO_COLOR", "").lower() in ["true", "1", "yes", "y"]
    ch_no_rich = os.getenv("CH_NO_RICH", "").lower() in ["true", "1", "yes", "y"]

    return not (no_color or ch_no_color or ch_no_rich)


def is_otel_enabled() -> bool:
    """Проверяет, доступен ли OpenTelemetry и не отключен ли он.

    Учитывает:
    - Наличие установленного пакета opentelemetry.
    - Переменную окружения CH_DISABLE_TRACING

    Returns:
        True, если OpenTelemetry трассировка включена и доступна.
    """
    if not OTEL_AVAILABLE:
        return False

    return os.getenv("CH_DISABLE_TRACING", "").lower() not in ["true", "1", "yes", "y"]
