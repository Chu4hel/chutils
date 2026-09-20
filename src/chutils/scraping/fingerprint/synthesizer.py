"""Единый фасад синтезатора цифровых отпечатков (FingerprintSynthesizer)."""

from __future__ import annotations

import importlib.util
from typing import Literal

from .external import BrowserForgeProvider
from .models import FingerprintProfile
from .procedural import ProceduralSynthesizer


class FingerprintSynthesizer:
    """Интеллектуальный синтезатор цифровой личности браузера с поддержкой процедурного и байесовского режимов."""

    def __init__(
        self,
        mode: Literal["auto", "procedural", "browserforge", "fpgen"] = "auto",
        os_target: str = "windows",
        locale: str = "ru-RU",
    ) -> None:
        """Инициализирует синтезатор.

        Args:
            mode: Режим работы ('auto', 'procedural', 'browserforge', 'fpgen').
                В режиме 'auto' при наличии сида всегда используется детерминированный процедурный генератор.
                Если сид не передан, при наличии browserforge используется он, иначе процедурный.
            os_target: Целевая операционная система ('windows', 'macos', 'linux').
            locale: Локаль системы для подбора периферийных устройств.
        """
        self.mode = mode
        self.os_target = os_target
        self.locale = locale
        self._procedural = ProceduralSynthesizer(os_target=os_target, locale=locale)

    def synthesize(self, seed: int | str | None = None) -> FingerprintProfile:
        """Синтезирует отпечаток цифровой личности.

        Args:
            seed: Сид профиля для детерминированной генерации.

        Returns:
            Экземпляр FingerprintProfile с физически согласованными характеристиками.
        """
        if self.mode == "procedural":
            return self._procedural.synthesize(seed)

        if self.mode == "browserforge":
            provider = BrowserForgeProvider(browser="chrome", os=self.os_target)
            return provider.generate(seed)

        # Режим 'auto'
        if seed is not None:
            # При наличии сида строгая детерминированность гарантируется процедурным движком
            return self._procedural.synthesize(seed)

        # Без сида: проверяем наличие browserforge
        if importlib.util.find_spec("browserforge") is not None:
            try:
                provider = BrowserForgeProvider(browser="chrome", os=self.os_target)
                return provider.generate(seed)
            except Exception:
                pass

        return self._procedural.synthesize(seed)

    @staticmethod
    def is_browserforge_available() -> bool:
        """Проверяет, установлена ли библиотека browserforge.

        Returns:
            True, если библиотека найдена и доступна для импорта, иначе False.
        """
        return importlib.util.find_spec("browserforge") is not None

    @staticmethod
    def is_fpgen_available() -> bool:
        """Проверяет, установлена ли библиотека fpgen.

        Returns:
            True, если библиотека найдена и доступна для импорта, иначе False.
        """
        return importlib.util.find_spec("fpgen") is not None

    @classmethod
    def create_procedural(
        cls,
        seed: int | str | None = None,
        os_target: str = "windows",
        locale: str = "ru-RU",
    ) -> FingerprintProfile:
        """Быстрый хелпер создания чисто процедурного отпечатка.

        Args:
            seed: Опциональный сид для повторяемой генерации отпечатка.
            os_target: Имя целевой ОС ('windows', 'macos', 'linux').
            locale: Локаль системы для подбора периферии.

        Returns:
            Экземпляр FingerprintProfile с физически валидным отпечатком.
        """
        return cls(mode="procedural", os_target=os_target, locale=locale).synthesize(seed)

    @classmethod
    def create_from_browserforge(
        cls,
        browser: str = "chrome",
        os_target: str = "windows",
    ) -> FingerprintProfile:
        """Быстрый хелпер создания отпечатка через библиотеку browserforge.

        Args:
            browser: Тип эмулируемого браузера ('chrome', 'firefox', 'safari').
            os_target: Целевая ОС ('windows', 'macos', 'linux').

        Returns:
            Экземпляр FingerprintProfile, созданный обученной байесовской сетью.
        """
        return cls(mode="browserforge", os_target=os_target).synthesize()
