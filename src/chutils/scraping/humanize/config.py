"""Декларативная конфигурация антидетекта для браузерных движков."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .antidetect_scripts import (
    DEFAULT_DEVICE_MEMORY,
    DEFAULT_HARDWARE_CONCURRENCY,
    DEFAULT_WEBGL_RENDERER,
    DEFAULT_WEBGL_VENDOR,
)


class AntidetectConfig(BaseModel):
    """Конфигурация параметров маскировки браузера (антидетект)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    webgl_vendor: str = Field(
        default=DEFAULT_WEBGL_VENDOR,
        description="Эмулируемый производитель WebGL.",
    )
    webgl_renderer: str = Field(
        default=DEFAULT_WEBGL_RENDERER,
        description="Эмулируемая видеокарта WebGL.",
    )
    hardware_concurrency: int = Field(
        default=DEFAULT_HARDWARE_CONCURRENCY,
        ge=1,
        le=128,
        description="Количество виртуальных ядер процессора.",
    )
    device_memory: int = Field(
        default=DEFAULT_DEVICE_MEMORY,
        ge=1,
        le=128,
        description="Объем оперативной памяти устройства в ГБ.",
    )
    stealth_minimal: bool = Field(
        default=True,
        description=(
            "Если True, не накладывать синтетический шум на Canvas и не подменять WebGL, "
            "сохраняя 100% консистентный отпечаток реального Chromium (рекомендуется для nodriver)."
        ),
    )
    session_seed: str | int = Field(
        default=1337,
        description="Сид для детерминированного шума Canvas и AudioContext.",
    )
    client_hints: dict[str, Any] | None = Field(
        default=None,
        description="Параметры navigator.userAgentData (brands, platform, mobile).",
    )

    @classmethod
    def preset_stealth_nodriver(
        cls,
        *,
        session_seed: str | int = 1337,
        client_hints: dict[str, Any] | None = None,
    ) -> AntidetectConfig:
        """Рекомендуемый пресет для nodriver: zero-footprint (без синтетического шума Canvas/WebGL).

        Args:
            session_seed: Сид для детерминированного генератора псевдослучайных чисел.
            client_hints: Опциональный словарь с параметрами Client Hints.

        Returns:
            Экземпляр AntidetectConfig с конфигурацией zero-footprint.
        """
        return cls(
            stealth_minimal=True,
            session_seed=session_seed,
            client_hints=client_hints,
        )

    @classmethod
    def preset_aggressive(
        cls,
        *,
        webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
        webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
        hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
        device_memory: int = DEFAULT_DEVICE_MEMORY,
        session_seed: str | int = 1337,
        client_hints: dict[str, Any] | None = None,
    ) -> AntidetectConfig:
        """Агрессивный пресет с рандомизацией Canvas/WebGL/Audio (для Playwright/Selenium в headless).

        Args:
            webgl_vendor: Эмулируемый производитель WebGL.
            webgl_renderer: Эмулируемая видеокарта WebGL.
            hardware_concurrency: Эмулируемое количество ядер CPU.
            device_memory: Эмулируемый объем оперативной памяти в ГБ.
            session_seed: Сид для рандомизации шума Canvas/Audio.
            client_hints: Дополнительные параметры Client Hints.

        Returns:
            Экземпляр AntidetectConfig с агрессивной рандомизацией.
        """
        return cls(
            webgl_vendor=webgl_vendor,
            webgl_renderer=webgl_renderer,
            hardware_concurrency=hardware_concurrency,
            device_memory=device_memory,
            stealth_minimal=False,
            session_seed=session_seed,
            client_hints=client_hints,
        )

    @classmethod
    def preset_minimal(
        cls,
        *,
        session_seed: str | int = 1337,
    ) -> AntidetectConfig:
        """Минимальный пресет: отключен шум, только базовая защита от утечек и скрытие webdriver.

        Args:
            session_seed: Сид для инициализации сессии.

        Returns:
            Экземпляр AntidetectConfig с минимальной модификацией.
        """
        return cls(
            stealth_minimal=True,
            session_seed=session_seed,
        )

    def get_behavioral_profile(self) -> Any:
        """Возвращает детерминированный биометрический профиль моторики на основе session_seed.

        Returns:
            Экземпляр BehavioralProfile.
        """
        from .behavior import BehavioralProfile

        return BehavioralProfile.from_seed(self.session_seed)

    def get_init_script(self) -> str:
        """Генерирует JavaScript-скрипт антидетекта на основе настроек конфигурации.

        Returns:
            Строка исполняемого JavaScript-кода для инъекции в браузер.
        """
        from .antidetect_scripts import _get_antidetect_js

        return _get_antidetect_js(
            webgl_vendor=self.webgl_vendor,
            webgl_renderer=self.webgl_renderer,
            hardware_concurrency=self.hardware_concurrency,
            device_memory=self.device_memory,
            stealth_minimal=self.stealth_minimal,
            session_seed=self.session_seed,
            client_hints=self.client_hints,
        )

    async def apply_to_nodriver(self, tab: Any) -> None:
        """Применяет данную конфигурацию антидетекта к вкладке nodriver Tab.

        Args:
            tab: Экземпляр вкладки nodriver Tab.
        """
        from .antidetect import apply_antidetect_nodriver

        await apply_antidetect_nodriver(tab, config=self)

    async def apply_to_playwright(self, target: Any) -> None:
        """Применяет данную конфигурацию антидетекта к Playwright Page или BrowserContext.

        Args:
            target: Экземпляр Playwright BrowserContext или Page.
        """
        from .antidetect import apply_antidetect_playwright

        await apply_antidetect_playwright(target, config=self)

    def apply_to_selenium(self, driver: Any) -> None:
        """Применяет данную конфигурацию антидетекта к Selenium WebDriver.

        Args:
            driver: Экземпляр Selenium WebDriver.
        """
        from .antidetect import apply_antidetect_selenium

        apply_antidetect_selenium(driver, config=self)
