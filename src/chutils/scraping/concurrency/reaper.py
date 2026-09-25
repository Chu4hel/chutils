"""Модуль мониторинга неактивности и автоматического высвобождения браузеров (Scale-to-Zero)."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from chutils.logger import setup_logger

logger = setup_logger(__name__)

T = TypeVar("T")


class IdleReaperConfig(BaseModel):
    """Декларативная конфигурация сторожевого таймера неактивности и Scale-to-Zero."""

    model_config = ConfigDict(validate_assignment=True, extra="ignore")

    idle_timeout_seconds: float = Field(
        default=120.0,
        ge=0.0,
        description="Таймаут неактивности для избыточных инстансов (когда активно >1). 0 — отключить.",
    )
    scale_to_zero_seconds: float = Field(
        default=300.0,
        ge=0.0,
        description="Таймаут неактивности для закрытия последнего инстанса (Scale-to-Zero). 0 — отключить.",
    )
    check_interval_seconds: float = Field(
        default=15.0,
        gt=0.0,
        description="Периодичность фоновой проверки в секундах.",
    )
    enabled: bool = Field(
        default=True,
        description="Флаг активности сторожевого таймера. Если False, закрытие инстансов не производится.",
    )

    @classmethod
    def preset_aggressive(cls) -> IdleReaperConfig:
        """Агрессивный пресет для экономии RAM: сброс избыточных за 30с, Scale-to-Zero за 60с.

        Returns:
            Экземпляр IdleReaperConfig с агрессивными параметрами.
        """
        return cls(
            idle_timeout_seconds=30.0,
            scale_to_zero_seconds=60.0,
            check_interval_seconds=5.0,
        )

    @classmethod
    def preset_relaxed(cls) -> IdleReaperConfig:
        """Щадящий пресет для интерактивной работы: сброс избыточных за 5 мин, Scale-to-Zero за 15 мин.

        Returns:
            Экземпляр IdleReaperConfig с умеренными параметрами.
        """
        return cls(
            idle_timeout_seconds=300.0,
            scale_to_zero_seconds=900.0,
            check_interval_seconds=30.0,
        )

    @classmethod
    def preset_keep_warm(cls) -> IdleReaperConfig:
        """Пресет с удержанием 1 постоянного прогретого инстанса (Scale-to-Zero отключен).

        Returns:
            Экземпляр IdleReaperConfig с отключенным Scale-to-Zero.
        """
        return cls(
            idle_timeout_seconds=120.0,
            scale_to_zero_seconds=0.0,
            check_interval_seconds=15.0,
        )

    @classmethod
    def from_settings(
        cls,
        section: str = "reaper",
        config_dict: dict[str, Any] | None = None,
        **overrides: Any,
    ) -> IdleReaperConfig:
        """Загружает параметры из секции конфигурации chutils или переданного словаря.

        Args:
            section: Имя секции конфигурационного файла (по умолчанию 'reaper').
            config_dict: Явный словарь настроек. Если None, данные извлекаются через chutils.config.
            **overrides: Точечные переопределения параметров.

        Returns:
            Экземпляр IdleReaperConfig.
        """
        data: dict[str, Any] = {}
        if config_dict is not None:
            data.update(config_dict)
        else:
            try:
                from chutils.config.getters import get_config_value

                raw_idle = get_config_value(section, "idle_timeout_seconds", fallback=None)
                if raw_idle is not None:
                    data["idle_timeout_seconds"] = float(raw_idle)

                raw_s2z = get_config_value(section, "scale_to_zero_seconds", fallback=None)
                if raw_s2z is not None:
                    data["scale_to_zero_seconds"] = float(raw_s2z)

                raw_interval = get_config_value(
                    section, "check_interval_seconds", fallback=None
                )
                if raw_interval is not None:
                    data["check_interval_seconds"] = float(raw_interval)

                raw_enabled = get_config_value(section, "enabled", fallback=None)
                if raw_enabled is not None:
                    data["enabled"] = bool(raw_enabled)
            except Exception:
                pass

        data.update(overrides)
        return cls(**data)


IdleBrowserReaperConfig = IdleReaperConfig


class IdleBrowserReaper(Generic[T]):
    """Сторожевой таймер неактивности (Watchdog) для пула браузеров и воркеров с поддержкой Scale-to-Zero.

    Отслеживает время последнего использования (last_active_time) активных воркеров/браузеров
    и автоматически инициирует корректное завершение простаивающих процессов для освобождения RAM.
    Поддерживает двухуровневый таймаут:
    1. idle_timeout_seconds — для избыточных инстансов (когда активно >1).
    2. scale_to_zero_seconds — для закрытия последнего оставшегося инстанса при полном бездействии.
    """

    def __init__(
        self,
        close_worker_fn: Callable[[T], Awaitable[None] | None],
        is_worker_busy_fn: Callable[[T], bool],
        get_active_workers_fn: Callable[[], list[T]],
        get_last_used_fn: Callable[[T], float],
        config: IdleReaperConfig | None = None,
        *,
        idle_timeout_seconds: float | None = None,
        scale_to_zero_seconds: float | None = None,
        check_interval_seconds: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Инициализирует сборщик простаивающих воркеров.

        Args:
            close_worker_fn: Функция (синхронная или асинхронная) корректного закрытия воркера.
            is_worker_busy_fn: Функция проверки, выполняет ли воркер в данный момент задачу.
            get_active_workers_fn: Функция получения списка идентификаторов запущенных воркеров.
            get_last_used_fn: Функция получения timestamp последнего использования воркера.
            config: Экземпляр IdleReaperConfig с готовыми настройками.
            idle_timeout_seconds: Таймаут неактивности для избыточных инстансов (переопределяет config).
            scale_to_zero_seconds: Таймаут неактивности для Scale-to-Zero (переопределяет config).
            check_interval_seconds: Периодичность проверки в секундах (переопределяет config).
            enabled: Флаг включения очистки (переопределяет config).
        """
        self._close_worker_fn = close_worker_fn
        self._is_worker_busy_fn = is_worker_busy_fn
        self._get_active_workers_fn = get_active_workers_fn
        self._get_last_used_fn = get_last_used_fn

        base_config = config.model_copy() if config is not None else IdleReaperConfig()
        overrides: dict[str, Any] = {}
        if idle_timeout_seconds is not None:
            overrides["idle_timeout_seconds"] = idle_timeout_seconds
        if scale_to_zero_seconds is not None:
            overrides["scale_to_zero_seconds"] = scale_to_zero_seconds
        if check_interval_seconds is not None:
            overrides["check_interval_seconds"] = check_interval_seconds
        if enabled is not None:
            overrides["enabled"] = enabled

        self._config = (
            base_config.model_copy(update=overrides) if overrides else base_config
        )
        self._task: asyncio.Task[None] | None = None

    @classmethod
    def from_config(
        cls,
        close_worker_fn: Callable[[T], Awaitable[None] | None],
        is_worker_busy_fn: Callable[[T], bool],
        get_active_workers_fn: Callable[[], list[T]],
        get_last_used_fn: Callable[[T], float],
        config: IdleReaperConfig | None = None,
        config_section: str = "reaper",
        **overrides: Any,
    ) -> IdleBrowserReaper[T]:
        """Создает экземпляр с автоматическим чтением параметров из конфигурации chutils.

        Args:
            close_worker_fn: Функция закрытия инстанса воркера/браузера.
            is_worker_busy_fn: Функция проверки занятости воркера выполнением задачи.
            get_active_workers_fn: Функция получения списка всех активных воркеров.
            get_last_used_fn: Функция получения timestamp последнего использования воркера.
            config: Готовый объект конфигурации.
            config_section: Название секции в файле настроек.
            **overrides: Переопределения отдельных параметров конфигурации.

        Returns:
            Инициализированный экземпляр IdleBrowserReaper.
        """
        cfg = config or IdleReaperConfig.from_settings(
            section=config_section, **overrides
        )
        return cls(
            close_worker_fn=close_worker_fn,
            is_worker_busy_fn=is_worker_busy_fn,
            get_active_workers_fn=get_active_workers_fn,
            get_last_used_fn=get_last_used_fn,
            config=cfg,
        )

    def configure(
        self,
        config: IdleReaperConfig | None = None,
        *,
        idle_timeout_seconds: float | None = None,
        scale_to_zero_seconds: float | None = None,
        check_interval_seconds: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Динамически обновляет настройки сторожевого таймера на лету.

        Args:
            config: Новый базовый объект конфигурации.
            idle_timeout_seconds: Таймаут неактивности для завершения избыточных инстансов.
            scale_to_zero_seconds: Таймаут полного простоя до закрытия последнего инстанса.
            check_interval_seconds: Интервал регулярной проверки.
            enabled: Флаг активности таймера.
        """
        base = config.model_copy() if config is not None else self._config
        overrides: dict[str, Any] = {}
        if idle_timeout_seconds is not None:
            overrides["idle_timeout_seconds"] = idle_timeout_seconds
        if scale_to_zero_seconds is not None:
            overrides["scale_to_zero_seconds"] = scale_to_zero_seconds
        if check_interval_seconds is not None:
            overrides["check_interval_seconds"] = check_interval_seconds
        if enabled is not None:
            overrides["enabled"] = enabled

        self._config = base.model_copy(update=overrides) if overrides else base

    @property
    def config(self) -> IdleReaperConfig:
        """Текущая конфигурация сторожевого таймера."""
        return self._config

    @property
    def is_running(self) -> bool:
        """Запущен ли фоновый мониторинг."""
        return self._task is not None and not self._task.done()

    @property
    def enabled(self) -> bool:
        """Включена ли очистка простаивающих ресурсов."""
        return self._config.enabled

    @property
    def idle_timeout_seconds(self) -> float:
        """Таймаут простоя избыточных инстансов."""
        return self._config.idle_timeout_seconds

    @property
    def scale_to_zero_seconds(self) -> float:
        """Таймаут полного Scale-to-Zero."""
        return self._config.scale_to_zero_seconds

    @property
    def check_interval_seconds(self) -> float:
        """Интервал фоновой проверки."""
        return self._config.check_interval_seconds

    def start(self) -> None:
        """Запускает фоновую задачу периодической очистки, если она еще не запущена."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Останавливает фоновую задачу мониторинга."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

    async def __aenter__(self) -> IdleBrowserReaper[T]:
        """Асинхронный контекстный менеджер для автоматического старта."""
        self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Асинхронный контекстный менеджер для автоматической остановки."""
        await self.stop()

    async def _close_worker(self, worker: T) -> None:
        """Внутренний вызов закрытия воркера с поддержкой синхронных и асинхронных коллбэков."""
        res = self._close_worker_fn(worker)
        if inspect.isawaitable(res):
            await res

    async def reap(self) -> int:
        """Выполняет одну итерацию проверки и закрывает простаивающие браузеры.

        Returns:
            Количество закрытых экземпляров браузеров / воркеров.
        """
        if not self._config.enabled:
            return 0

        now = time.time()
        active_workers = self._get_active_workers_fn()
        sorted_workers = sorted(
            active_workers,
            key=lambda w: self._get_last_used_fn(w),
        )
        total_active = len(sorted_workers)
        closed_count = 0

        for worker in sorted_workers:
            if self._is_worker_busy_fn(worker):
                continue

            last_used = self._get_last_used_fn(worker)
            idle_duration = max(0.0, now - last_used)

            # 1. Избыточный инстанс (активно > 1) и превышен idle_timeout
            if (
                total_active > 1
                and self._config.idle_timeout_seconds > 0
                and idle_duration >= self._config.idle_timeout_seconds
            ):
                logger.info(
                    "Экземпляр '%s' не использовался %.1f сек (таймаут: %.1f сек). "
                    "Закрытие избыточного браузера для экономии RAM...",
                    worker,
                    idle_duration,
                    self._config.idle_timeout_seconds,
                )
                await self._close_worker(worker)
                total_active -= 1
                closed_count += 1
                continue

            # 2. Полный Scale-to-Zero (остался 1 инстанс) и превышен scale_to_zero_timeout
            if (
                total_active == 1
                and self._config.scale_to_zero_seconds > 0
                and idle_duration >= self._config.scale_to_zero_seconds
            ):
                logger.info(
                    "Все экземпляры бездействовали %.1f сек (таймаут scale-to-zero: %.1f сек). "
                    "Закрытие последнего браузера '%s' (Scale-to-Zero)...",
                    idle_duration,
                    self._config.scale_to_zero_seconds,
                    worker,
                )
                await self._close_worker(worker)
                total_active -= 1
                closed_count += 1
                break

        return closed_count

    async def _run_loop(self) -> None:
        """Внутренний бесконечный цикл периодической проверки."""
        while True:
            try:
                await asyncio.sleep(self._config.check_interval_seconds)
                await self.reap()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "Ошибка в фоновом цикле очистки простаивающих браузеров: %s", exc
                )


IdleReaper = IdleBrowserReaper
