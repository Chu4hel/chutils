"""Адаптеры для внешних генераторов отпечатков (browserforge, fpgen)."""

from __future__ import annotations

import hashlib
import importlib.util
import random

from chutils.exceptions import OptionalDependencyError

from .models import (
    AudioFingerprint,
    FingerprintProfile,
    HardwareFingerprint,
    ScreenFingerprint,
    WebGLFingerprint,
)

try:
    from browserforge.fingerprints import FingerprintGenerator
except ImportError:
    FingerprintGenerator = None  # type: ignore[assignment,misc]


def _ensure_browserforge() -> None:
    """Проверяет доступность библиотеки browserforge."""
    try:
        if importlib.util.find_spec("browserforge") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Модуль 'browserforge' не установлен. Для использования байесовской генерации "
            "установите его: pip install browserforge или pip install chutils[fingerprint].",
            dependency="browserforge",
            hint="Выполните pip install browserforge",
        )


def _ensure_fpgen() -> None:
    """Проверяет доступность библиотеки fpgen."""
    try:
        if importlib.util.find_spec("fpgen") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Модуль 'fpgen' не установлен. Для использования fpgen "
            "установите его: pip install fpgen.",
            dependency="fpgen",
            hint="Выполните pip install fpgen",
        )


class BrowserForgeProvider:
    """Провайдер генерации отпечатков через библиотеку browserforge (Apify)."""

    def __init__(self, browser: str = "chrome", os: str = "windows") -> None:
        """Инициализирует провайдер browserforge."""
        self.browser = browser.lower()
        self.os = os.lower()

    def generate(self, seed: int | str | None = None) -> FingerprintProfile:
        """Генерирует профиль через обученную байесовскую сеть browserforge.

        При передаче seed генерация полностью детерминизируется с изоляцией
        состояния встроенного генератора случайных чисел (PRNG).

        Args:
            seed: Опциональный сид для воспроизводимой генерации.

        Returns:
            Экземпляр FingerprintProfile.
        """
        _ensure_browserforge()
        generator_cls = globals().get("FingerprintGenerator")
        if generator_cls is None:
            try:
                from browserforge.fingerprints import FingerprintGenerator as _FG

                generator_cls = _FG
            except ImportError:
                generator_cls = None

        if generator_cls is None:
            raise OptionalDependencyError(
                "Модуль 'browserforge' не найден.",
                dependency="browserforge",
            )

        fg = generator_cls(browser=self.browser, os=self.os)
        if seed is not None:
            seed_bytes = str(seed).encode("utf-8")
            seed_int = int(hashlib.sha256(seed_bytes).hexdigest(), 16) % (2**32)
            rng_state = random.getstate()
            try:
                random.seed(seed_int)
                raw_fp = fg.generate()
            finally:
                random.setstate(rng_state)
        else:
            raw_fp = fg.generate()

        nav = raw_fp.navigator
        scr = raw_fp.screen
        video = raw_fp.videoCard

        return FingerprintProfile(
            seed=seed,
            os=self.os,
            browser=self.browser,
            user_agent=getattr(nav, "userAgent", ""),
            webgl=WebGLFingerprint(
                vendor=getattr(video, "vendor", "Google Inc. (NVIDIA)"),
                renderer=getattr(video, "renderer", ""),
            ),
            screen=ScreenFingerprint(
                width=getattr(scr, "width", 1920),
                height=getattr(scr, "height", 1080),
                avail_width=getattr(scr, "availWidth", 1920),
                avail_height=getattr(scr, "availHeight", 1040),
                device_pixel_ratio=float(getattr(scr, "devicePixelRatio", 1.0)),
                color_depth=int(getattr(scr, "colorDepth", 24)),
            ),
            hardware=HardwareFingerprint(
                concurrency=int(getattr(nav, "hardwareConcurrency", 8)),
                memory_gb=int(getattr(nav, "deviceMemory", 8)),
            ),
            audio=AudioFingerprint(),
            media_devices=[],
            client_hints=getattr(raw_fp, "headers", {}),
            source="browserforge",
        )
