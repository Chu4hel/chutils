from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable, Awaitable

from chutils.decorators import timeout as timeout_decorator
from .models import CheckResult, HealthReport


class DiagnosticsManager:
    """Класс-оркестратор для регистрации и выполнения диагностических проверок.

    Управляет реестром встроенных и кастомных проверок работоспособности,
    выполняет их с контролем таймаутов и формирует итоговый отчет.
    """

    def __init__(self) -> None:
        """Инициализирует менеджер диагностики."""
        self._checks: list[dict[str, str | bool | float | Callable[..., bool | str | tuple[bool, str] | Awaitable[bool | str | tuple[bool, str]]]]] = []

    def register(
        self,
        name: str,
        critical: bool = True,
        timeout: float = 2.0,
    ) -> Callable[[Callable[..., bool | str | tuple[bool, str] | Awaitable[bool | str | tuple[bool, str]]]], Callable[..., bool | str | tuple[bool, str] | Awaitable[bool | str | tuple[bool, str]]]]:
        """Декоратор для регистрации функции проверки.

        Args:
            name: Уникальное название проверки.
            critical: Является ли проверка критической для работоспособности системы.
            timeout: Максимальное время выполнения проверки в секундах.

        Returns:
            Декоратор, который регистрирует функцию и возвращает её без изменений.
        """
        def decorator(
            func: Callable[..., bool | str | tuple[bool, str] | Awaitable[bool | str | tuple[bool, str]]]
        ) -> Callable[..., bool | str | tuple[bool, str] | Awaitable[bool | str | tuple[bool, str]]]:
            self.add_check(func, name, critical, timeout)
            return func
        return decorator

    def add_check(
        self,
        func: Callable[..., bool | str | tuple[bool, str] | Awaitable[bool | str | tuple[bool, str]]],
        name: str,
        critical: bool = True,
        timeout: float = 2.0,
    ) -> None:
        """Добавляет функцию проверки в реестр.

        Args:
            func: Функция проверки (синхронная или асинхронная).
            name: Уникальное название проверки.
            critical: Является ли проверка критической.
            timeout: Таймаут выполнения в секундах.
        """
        self._checks.append({
            "func": func,
            "name": name,
            "critical": critical,
            "timeout": timeout,
        })

    async def _run_single_check(
        self,
        check: dict[str, str | bool | float | Callable[..., bool | str | tuple[bool, str] | Awaitable[bool | str | tuple[bool, str]]]]
    ) -> CheckResult:
        """Выполняет одну диагностическую проверку с контролем таймаута.

        Args:
            check: Словарь с метаданными и функцией проверки.

        Returns:
            Результат выполнения проверки CheckResult.
        """
        from typing import cast, Any

        name = str(check["name"])
        critical = bool(check["critical"])
        timeout_val = float(cast(Any, check["timeout"]))
        func = cast(Callable[..., Any], check["func"])

        # Оборачиваем функцию декоратором таймаута из chutils
        func_with_timeout = timeout_decorator(timeout_val)(func)

        start_time = time.perf_counter()
        success = False
        error_msg: str | None = None
        message: str | None = None

        try:
            if inspect.iscoroutinefunction(func):
                res = await func_with_timeout()
            else:
                res = await asyncio.to_thread(func_with_timeout)

            # Интерпретируем результат
            if isinstance(res, tuple):
                if len(res) == 2:
                    success = bool(res[0])
                    message = str(res[1])
                else:
                    success = bool(res[0]) if res else False
            elif isinstance(res, bool):
                success = res
                message = "Проверка пройдена" if success else "Проверка завершилась неудачно"
            elif isinstance(res, str):
                success = True
                message = res
            else:
                success = True
                message = str(res) if res is not None else "Проверка завершена успешно"
        except Exception as e:
            success = False
            error_msg = f"{type(e).__name__}: {str(e)}"

        execution_time = time.perf_counter() - start_time
        return CheckResult(
            name=name,
            success=success,
            critical=critical,
            execution_time=execution_time,
            error=error_msg,
            message=message,
        )

    async def run_checks(self) -> HealthReport:
        """Асинхронно запускает все зарегистрированные проверки параллельно.

        Returns:
            Сводный отчет о работоспособности HealthReport.
        """
        start_time = time.perf_counter()

        if not self._checks:
            # Если проверок нет, система по умолчанию здорова
            return HealthReport(
                status="HEALTHY",
                results=[],
                total_time=time.perf_counter() - start_time
            )

        # Выполняем все проверки параллельно
        tasks = [self._run_single_check(check) for check in self._checks]
        results = await asyncio.gather(*tasks)

        # Вычисляем общий статус
        has_unhealthy_critical = any(not r.success for r in results if r.critical)
        has_unhealthy_noncritical = any(not r.success for r in results if not r.critical)

        if has_unhealthy_critical:
            status = "UNHEALTHY"
        elif has_unhealthy_noncritical:
            status = "DEGRADED"
        else:
            status = "HEALTHY"

        total_time = time.perf_counter() - start_time
        return HealthReport(
            status=status,
            results=results,
            total_time=total_time
        )

    def run_checks_sync(self) -> HealthReport:
        """Синхронная обертка для запуска проверок.

        Использует текущий или создаёт новый цикл событий для запуска run_checks.

        Returns:
            Сводный отчет о работоспособности HealthReport.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Если мы уже находимся внутри асинхронного цикла, запускаем через run_until_complete
            # в отдельном потоке с новым циклом событий, чтобы не блокировать текущий.
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, self.run_checks())
                return future.result()
        else:
            return asyncio.run(self.run_checks())


# Создаем глобальный экземпляр менеджера по умолчанию
default_manager = DiagnosticsManager()


@default_manager.register("keyring", critical=False, timeout=2.0)
def check_keyring() -> tuple[bool, str]:
    """Встроенная проверка доступности хранилища секретов keyring.

    Returns:
        Кортеж (успех, сообщение).
    """
    from chutils.secret_manager.providers import KEYRING_AVAILABLE
    if not KEYRING_AVAILABLE:
        return False, "Библиотека keyring не установлена или не поддерживается."

    import keyring
    from keyring.errors import NoKeyringError
    try:
        service = "chutils_healthcheck"
        key = "test_key"
        val = "test_val"
        keyring.set_password(service, key, val)
        retrieved = keyring.get_password(service, key)
        keyring.delete_password(service, key)
        if retrieved == val:
            return True, "Хранилище секретов (keyring) доступно и работает корректно."
        else:
            return False, f"Записанное значение не совпадает с прочитанным ({retrieved} != {val})"
    except NoKeyringError:
        return False, "Системное хранилище секретов недоступно (NoKeyringError)."
    except Exception as e:
        return False, f"Ошибка при обращении к keyring: {e}"


@default_manager.register("config", critical=True, timeout=2.0)
def check_config() -> tuple[bool, str]:
    """Встроенная проверка целостности и валидности конфигурационных файлов.

    Returns:
        Кортеж (успех, сообщение).
    """
    from chutils import get_config_file_path, get_config
    import os

    config_path = get_config_file_path()
    if not config_path:
        return True, "Файлы конфигурации не найдены (используются значения по умолчанию/переменные окружения)."

    if not os.path.exists(config_path):
        return False, f"Файл конфигурации {config_path} не найден на диске."

    try:
        get_config()
        return True, f"Конфигурация успешно загружена из файла: {config_path}"
    except Exception as e:
        return False, f"Ошибка парсинга/загрузки конфигурации: {e}"
