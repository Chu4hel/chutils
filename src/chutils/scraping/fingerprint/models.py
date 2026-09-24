# chutils: ignore[CodeDecompositionRule]
"""Pydantic-модели профиля цифрового отпечатка (Fingerprint Profile)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from chutils.fs import atomic_write, ensure_dir

if TYPE_CHECKING:
    from chutils.scraping.humanize.config import AntidetectConfig


class WebGLFingerprint(BaseModel):
    """Параметры графического стека WebGL."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    vendor: str = Field(
        default="Google Inc. (NVIDIA)",
        description="Вендор WebGL (UNMASKED_VENDOR_WEBGL).",
    )
    renderer: str = Field(
        default="ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11-31.0.15.5186)",
        description="Строка рендерера WebGL (UNMASKED_RENDERER_WEBGL).",
    )


class ScreenFingerprint(BaseModel):
    """Геометрия и характеристики дисплея."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    width: int = Field(default=1920, description="Полная ширина экрана в пикселях.")
    height: int = Field(default=1080, description="Полная высота экрана в пикселях.")
    avail_width: int = Field(
        default=1920, description="Доступная ширина экрана за вычетом панели задач."
    )
    avail_height: int = Field(
        default=1040, description="Доступная высота экрана за вычетом панели задач."
    )
    device_pixel_ratio: float = Field(
        default=1.0, description="Масштабирование дисплея (window.devicePixelRatio)."
    )
    color_depth: int = Field(
        default=24, description="Глубина цвета дисплея (screen.colorDepth)."
    )


class HardwareFingerprint(BaseModel):
    """Аппаратные ресурсы процессора и оперативной памяти."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    concurrency: int = Field(
        default=8,
        ge=1,
        le=128,
        description="Количество логических ядер процессора (navigator.hardwareConcurrency).",
    )
    memory_gb: int = Field(
        default=16,
        ge=1,
        le=128,
        description="Объем оперативной памяти устройства в ГБ (navigator.deviceMemory).",
    )


class AudioFingerprint(BaseModel):
    """Параметры аудиоподсистемы и микрошум дискретизации ЦАП."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    channel_count: int = Field(
        default=2, description="Количество аудиоканалов (стерео)."
    )
    sample_rate: int = Field(
        default=44100, description="Частота дискретизации аудио (Гц)."
    )
    noise_factor: float = Field(
        default=1e-7,
        description="Детерминированный субпиксельный аналоговый шум порядка 10^-7.",
    )


class MediaDeviceItem(BaseModel):
    """Элемент списка медиа-устройств (микрофон, динамики, камера)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    kind: str = Field(
        description="Тип устройства: 'audioinput', 'audiooutput' или 'videoinput'."
    )
    label: str = Field(description="Человекочитаемое имя устройства.")
    device_id: str = Field(description="Уникальный идентификатор устройства.")
    group_id: str = Field(description="Идентификатор группы устройства.")


class FingerprintProfile(BaseModel):
    """Полный синтезированный профиль цифровой личности браузера."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    seed: str | int | None = Field(
        default=None,
        description="Исходный сид сессии для детерминированной генерации.",
    )
    os: str = Field(default="windows", description="Целевая операционная система.")
    browser: str = Field(default="chrome", description="Эмулируемый браузер.")
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        description="Строка User-Agent.",
    )
    webgl: WebGLFingerprint = Field(
        default_factory=WebGLFingerprint, description="Отпечаток WebGL."
    )
    screen: ScreenFingerprint = Field(
        default_factory=ScreenFingerprint, description="Отпечаток экрана."
    )
    hardware: HardwareFingerprint = Field(
        default_factory=HardwareFingerprint, description="Отпечаток процессора и RAM."
    )
    audio: AudioFingerprint = Field(
        default_factory=AudioFingerprint, description="Отпечаток аудио."
    )
    media_devices: list[MediaDeviceItem] = Field(
        default_factory=list, description="Список эмулируемых медиаустройств."
    )
    client_hints: dict[str, Any] = Field(
        default_factory=dict, description="Словарь согласованных Client Hints."
    )
    source: str = Field(
        default="procedural",
        description="Источник генерации: 'procedural', 'browserforge' или 'fpgen'.",
    )

    def to_antidetect_config(self, stealth_minimal: bool = True) -> AntidetectConfig:
        """Конвертирует профиль в AntidetectConfig для браузерных движков.

        Args:
            stealth_minimal: Если True, не накладывать синтетический шум на Canvas.

        Returns:
            Экземпляр AntidetectConfig с параметрами профиля.
        """
        from chutils.scraping.humanize.config import AntidetectConfig

        seed_val = self.seed if self.seed is not None else 1337

        return AntidetectConfig(
            webgl_vendor=self.webgl.vendor,
            webgl_renderer=self.webgl.renderer,
            hardware_concurrency=self.hardware.concurrency,
            device_memory=self.hardware.memory_gb,
            stealth_minimal=stealth_minimal,
            session_seed=seed_val,
            client_hints=self.client_hints,
            user_agent=self.user_agent,
            screen_width=self.screen.width,
            screen_height=self.screen.height,
            screen_avail_height=self.screen.avail_height,
            device_pixel_ratio=self.screen.device_pixel_ratio,
        )

    def to_dict(self) -> dict[str, Any]:
        """Возвращает профиль в виде словаря.

        Returns:
            Словарь со всеми полями профиля.
        """
        return self.model_dump()

    def to_json(self, indent: int = 2) -> str:
        """Сериализует профиль в строку JSON.

        Args:
            indent: Размер отступа для форматирования.

        Returns:
            Строка профиля в формате JSON.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save_to_file(self, path: str | Path) -> None:
        """Сохраняет профиль в JSON файл на диске.

        Args:
            path: Путь к целевому файлу.
        """
        target = Path(path)
        ensure_dir(target.parent)
        atomic_write(target, self.to_json(), encoding="utf-8")

    @classmethod
    def from_file(cls, path: str | Path) -> FingerprintProfile:
        """Загружает профиль из сохраненного JSON файла.

        Args:
            path: Путь к файлу профиля.

        Returns:
            Восстановленный экземпляр FingerprintProfile.
        """
        target = Path(path)
        data = json.loads(target.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    async def apply_to_tab(self, tab: Any) -> None:
        """Применяет параметры отпечатка к вкладке nodriver Tab.

        Args:
            tab: Вкладка nodriver (Tab).
        """
        config = self.to_antidetect_config()
        await config.apply_to_nodriver(tab)

    async def apply_to_page(self, page: Any) -> None:
        """Применяет параметры отпечатка к странице Playwright Page.

        Args:
            page: Страница Playwright (Page).
        """
        config = self.to_antidetect_config()
        await config.apply_to_playwright(page)
