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
    screen_width: int | None = Field(
        default=None,
        description="Эмулируемая ширина экрана (screen.width).",
    )
    screen_height: int | None = Field(
        default=None,
        description="Эмулируемая высота экрана (screen.height).",
    )
    screen_avail_height: int | None = Field(
        default=None,
        description="Эмулируемая доступная высота экрана за вычетом панели задач (screen.availHeight).",
    )
    device_pixel_ratio: float | None = Field(
        default=None,
        description="Эмулируемый коэффициент масштабирования (window.devicePixelRatio).",
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

    @classmethod
    def from_fingerprint(
        cls,
        profile: Any,
        *,
        stealth_minimal: bool = True,
    ) -> AntidetectConfig:
        """Создает AntidetectConfig на основе объекта FingerprintProfile.

        Args:
            profile: Экземпляр FingerprintProfile.
            stealth_minimal: Если True, не накладывать синтетический шум на Canvas.

        Returns:
            Сконфигурированный экземпляр AntidetectConfig.
        """
        return profile.to_antidetect_config(stealth_minimal=stealth_minimal)

    @classmethod
    def from_seed(
        cls,
        seed: int | str,
        *,
        stealth_minimal: bool = True,
        os_target: str = "windows",
        locale: str = "ru-RU",
    ) -> AntidetectConfig:
        """Синтезирует детерминированную цифровую личность по сиду и возвращает AntidetectConfig.

        Один и тот же сид всегда дает абсолютно идентичный и физически согласованный
        отпечаток (видеокарта, процессор, память, геометрия экрана, панель задач).

        Args:
            seed: Сид профиля или имя учетной записи.
            stealth_minimal: Если True, сохраняет чистый отпечаток без искажения Canvas.
            os_target: Целевая ОС ('windows').
            locale: Локаль ('ru-RU', 'en-US').

        Returns:
            Экземпляр AntidetectConfig.
        """
        from chutils.scraping.fingerprint import FingerprintSynthesizer

        fp = FingerprintSynthesizer(mode="procedural", os_target=os_target, locale=locale).synthesize(seed)
        return fp.to_antidetect_config(stealth_minimal=stealth_minimal)

    @classmethod
    def from_browserforge(
        cls,
        seed: int | str | None = None,
        *,
        browser: str = "chrome",
        os: str = "windows",
        stealth_minimal: bool = True,
    ) -> AntidetectConfig:
        """Генерирует отпечаток через байесовскую сеть browserforge (при наличии пакета).

        Args:
            seed: Опциональный сид для воспроизводимой детерминированной генерации.
            browser: Эмулируемый браузер ('chrome').
            os: Целевая ОС ('windows').
            stealth_minimal: Режим маскировки.

        Returns:
            Экземпляр AntidetectConfig.
        """
        from chutils.scraping.fingerprint import FingerprintSynthesizer

        fp = FingerprintSynthesizer(mode="browserforge", os_target=os).synthesize(seed)
        return fp.to_antidetect_config(stealth_minimal=stealth_minimal)

    @classmethod
    def from_procedural(
        cls,
        seed: int | str | None = None,
        *,
        stealth_minimal: bool = True,
        os_target: str = "windows",
        locale: str = "ru-RU",
    ) -> AntidetectConfig:
        """Синтезирует отпечаток через встроенный процедурный генератор.

        Args:
            seed: Опциональный сид.
            stealth_minimal: Режим маскировки.
            os_target: Целевая ОС.
            locale: Локаль.

        Returns:
            Экземпляр AntidetectConfig.
        """
        from chutils.scraping.fingerprint import FingerprintSynthesizer

        fp = FingerprintSynthesizer(mode="procedural", os_target=os_target, locale=locale).synthesize(seed)
        return fp.to_antidetect_config(stealth_minimal=stealth_minimal)


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
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            screen_avail_height=self.screen_avail_height,
            device_pixel_ratio=self.device_pixel_ratio,
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
