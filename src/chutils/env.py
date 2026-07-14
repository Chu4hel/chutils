from __future__ import annotations

import importlib.util
import os
import typing as t

T = t.TypeVar("T", bound="BaseEnvManifest")


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


if PYDANTIC_AVAILABLE:
    import pydantic

    class BaseEnvManifest(pydantic.BaseModel):
        """Базовый манифест переменных окружения на базе Pydantic."""

        @classmethod
        def load(cls: type[T]) -> T:
            """Загружает и валидирует переменные окружения.

            Returns:
                Экземпляр провалидированного манифеста.

            Raises:
                EnvValidationError: Если валидация не прошла.
            """
            from chutils.exceptions import EnvValidationError

            data: dict[str, t.Any] = {}

            # Инициализация SecretManager для поиска отсутствующих секретов
            secret_mgr = None
            try:
                from chutils.secret_manager import SecretManager
                from chutils.config import get_config_value

                service_name = get_config_value("App", "name", None)
                if not service_name:
                    service_name = os.path.basename(os.getcwd())
                secret_mgr = SecretManager(service_name)
            except Exception:
                pass

            for field_name, field_info in cls.model_fields.items():
                val = os.environ.get(field_name)

                # Ищем в SecretManager, если переменная секретная и отсутствует в os.environ
                if val is None and secret_mgr is not None:
                    is_secret = False
                    extra = field_info.json_schema_extra
                    if isinstance(extra, dict):
                        is_secret = extra.get("secret") is True

                    if is_secret:
                        try:
                            val = secret_mgr.get_secret(field_name)
                        except Exception:
                            pass

                if val is not None:
                    data[field_name] = val

            try:
                return cls.model_validate(data)
            except Exception as e:
                if isinstance(e, pydantic.ValidationError):
                    errors = e.errors()

                    masked_errors = []
                    for err in errors:
                        masked_err = dict(err)
                        loc = err.get("loc", ())
                        if loc:
                            field_name = loc[0]
                            field_info = cls.model_fields.get(field_name)
                            if field_info:
                                extra = field_info.json_schema_extra
                                is_secret = False
                                if isinstance(extra, dict):
                                    is_secret = extra.get("secret") is True

                                if is_secret:
                                    if "input" in masked_err:
                                        masked_err["input"] = "***"
                        masked_errors.append(masked_err)

                    raise EnvValidationError(
                        "Ошибка валидации переменных окружения",
                        errors=masked_errors,
                        hint="Убедитесь, что все обязательные переменные окружения установлены и имеют корректные значения.",
                    ) from e
                raise e
else:
    class BaseEnvManifest:
        """Заглушка манифеста переменных окружения (Pydantic не установлен)."""

        @classmethod
        def load(cls: type[t.Any]) -> t.Any:
            """Пытается загрузить манифест без Pydantic.

            Returns:
                Метод никогда не возвращает значение, так как всегда вызывает исключение.

            Raises:
                OptionalDependencyError: Всегда выбрасывается, так как Pydantic отсутствует.
            """
            from chutils.exceptions import OptionalDependencyError

            raise OptionalDependencyError(
                "Pydantic не установлен.",
                dependency="pydantic",
                hint="Установите его: pip install chutils[pydantic]",
            )

