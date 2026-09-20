"""Биометрический профиль моторики и поведения пользователя (мышь, клавиатура)."""

from __future__ import annotations

import random
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .actions import async_click, async_type_text, click, type_text
from .math_utils import KeyboardTypoGenerator, WindMouseGenerator


class BehavioralProfile(BaseModel):
    """Конфигурация биометрического профиля моторики (скорость, задержки, опечатки, движение мыши)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    seed: int | str | None = Field(
        default=None,
        description="Исходный сид для детерминированной воспроизводимости профиля.",
    )
    speed_wpm: float = Field(
        default=45.0,
        ge=10.0,
        le=200.0,
        description="Скорость печати в словах в минуту (WPM).",
    )
    typo_rate: float = Field(
        default=0.03,
        ge=0.0,
        le=1.0,
        description="Вероятность опечатки на каждый вводимый символ.",
    )
    layout_error_rate: float = Field(
        default=0.02,
        ge=0.0,
        le=1.0,
        description="Вероятность ошибки раскладки в самом начале ввода.",
    )
    gravity: float = Field(
        default=9.0,
        ge=1.0,
        le=50.0,
        description="Сила гравитации траектории курсора WindMouse.",
    )
    wind: float = Field(
        default=3.0,
        ge=0.1,
        le=30.0,
        description="Сила случайного дрейфа (ветра) курсора WindMouse.",
    )
    max_step: float = Field(
        default=15.0,
        ge=1.0,
        le=100.0,
        description="Максимальный шаг смещения курсора WindMouse.",
    )
    target_area: float = Field(
        default=8.0,
        ge=1.0,
        le=50.0,
        description="Радиус целевой зоны замедления WindMouse.",
    )
    key_hold_time: tuple[float, float] = Field(
        default=(0.04, 0.09),
        description="Диапазон задержки удержания клавиши клавиатуры (keyDown -> keyUp) в секундах.",
    )
    click_hold_time: tuple[float, float] = Field(
        default=(0.05, 0.12),
        description="Диапазон задержки удержания кнопки мыши (mouseDown -> mouseUp) в секундах.",
    )
    paste_threshold: int | None = Field(
        default=None,
        ge=1,
        description="Порог длины текста (в символах) для адаптивной вставки через буфер обмена.",
    )
    paste_delay_before: tuple[float, float] = Field(
        default=(0.4, 1.0),
        description="Диапазон паузы обдумывания перед вставкой из буфера (в секундах).",
    )
    paste_delay_after: tuple[float, float] = Field(
        default=(0.3, 0.8),
        description="Диапазон паузы проверки после вставки из буфера (в секундах).",
    )

    @property
    def wpm(self) -> float:
        """Алиас для speed_wpm."""
        return self.speed_wpm

    @property
    def error_rate(self) -> float:
        """Алиас для typo_rate."""
        return self.typo_rate

    @classmethod
    def from_seed(cls, seed: int | str) -> BehavioralProfile:
        """Создает детерминированный биометрический профиль моторики на основе сида.

        Один и тот же сид всегда порождает абсолютно идентичные биометрические характеристики
        (скорость ввода, опечатки, физику мыши, интервалы удержания), что позволяет
        зафиксировать уникальный почерк конкретного аккаунта или браузерного профиля.

        Args:
            seed: Числовой или строковый сид сессии/аккаунта.

        Returns:
            Экземпляр BehavioralProfile с реалистичными биометрическими характеристиками.
        """
        rng = random.Random(seed)

        # Скорость печати: диапазон живого пользователя (32.0 - 75.0 WPM)
        speed_wpm = round(rng.uniform(32.0, 75.0), 1)

        # Вероятность опечаток: от 1.5% до 6%
        typo_rate = round(rng.uniform(0.015, 0.06), 3)

        # Ошибка раскладки в начале ввода: от 1% до 4%
        layout_error_rate = round(rng.uniform(0.01, 0.04), 3)

        # Физические параметры движения мыши WindMouse
        gravity = round(rng.uniform(7.5, 12.5), 2)
        wind = round(rng.uniform(2.0, 4.5), 2)
        max_step = round(rng.uniform(11.0, 19.0), 1)
        target_area = round(rng.uniform(6.0, 10.0), 1)

        # Время удержания клавиш при печати (мс)
        key_min = round(rng.uniform(0.03, 0.05), 3)
        key_max = round(key_min + rng.uniform(0.03, 0.05), 3)
        key_hold_time = (key_min, key_max)

        # Время удержания кнопки мыши при клике (мс)
        click_min = round(rng.uniform(0.04, 0.07), 3)
        click_max = round(click_min + rng.uniform(0.04, 0.07), 3)
        click_hold_time = (click_min, click_max)

        return cls(
            seed=seed,
            speed_wpm=speed_wpm,
            typo_rate=typo_rate,
            layout_error_rate=layout_error_rate,
            gravity=gravity,
            wind=wind,
            max_step=max_step,
            target_area=target_area,
            key_hold_time=key_hold_time,
            click_hold_time=click_hold_time,
        )

    def create_wind_mouse(self) -> WindMouseGenerator:
        """Создает генератор траекторий мыши WindMouse, настроенный под параметры профиля.

        Returns:
            Экземпляр WindMouseGenerator.
        """
        return WindMouseGenerator(
            gravity=self.gravity,
            wind=self.wind,
            max_step=self.max_step,
            target_area=self.target_area,
        )

    def create_typo_generator(self) -> KeyboardTypoGenerator:
        """Создает генератор опечаток клавиатуры, настроенный под параметры профиля.

        Returns:
            Экземпляр KeyboardTypoGenerator.
        """
        return KeyboardTypoGenerator(layout_error_rate=self.layout_error_rate)

    async def async_type_text(
        self,
        page: Any,
        selector: str,
        text: str,
        paste_threshold: int | None = None,
    ) -> None:
        """Вводит текст через Playwright / nodriver с биометрическими параметрами профиля.

        Args:
            page: Объект страницы Playwright Page или вкладки nodriver Tab.
            selector: CSS/XPath селектор поля ввода.
            text: Текст для ввода.
            paste_threshold: Порог адаптивной вставки через буфер (если None, берется из профиля).
        """
        threshold = self.paste_threshold if paste_threshold is None else paste_threshold
        await async_type_text(
            page=page,
            selector=selector,
            text=text,
            error_rate=self.typo_rate,
            speed_wpm=self.speed_wpm,
            key_hold_time=self.key_hold_time,
            layout_error_rate=self.layout_error_rate,
            paste_threshold=threshold,
            paste_delay_before=self.paste_delay_before,
            paste_delay_after=self.paste_delay_after,
        )

    async def async_click(
        self,
        page: Any,
        selector: str | None = None,
        x: int | None = None,
        y: int | None = None,
        start: tuple[int, int] | None = None,
        button: str = "left",
    ) -> None:
        """Выполняет клик по элементу или координатам с биометрией удержания кнопки мыши.

        Args:
            page: Объект страницы Playwright Page или вкладки nodriver Tab.
            selector: Селектор целевого элемента (опционально).
            x: Конечная координата X клика.
            y: Конечная координата Y клика.
            start: Начальные координаты курсора.
            button: Кнопка мыши ('left', 'right', 'middle').
        """
        await async_click(
            page=page,
            selector=selector,
            x=x,
            y=y,
            start=start,
            button=button,
            hold_time=self.click_hold_time,
        )

    def type_text(
        self,
        driver: Any,
        selector: str,
        text: str,
        paste_threshold: int | None = None,
    ) -> None:
        """Синхронно вводит текст через Selenium с биометрическими параметрами профиля.

        Args:
            driver: Экземпляр Selenium WebDriver.
            selector: CSS-селектор поля ввода.
            text: Текст для ввода.
            paste_threshold: Порог адаптивной вставки через буфер (если None, берется из профиля).
        """
        threshold = self.paste_threshold if paste_threshold is None else paste_threshold
        type_text(
            driver=driver,
            selector=selector,
            text=text,
            error_rate=self.typo_rate,
            speed_wpm=self.speed_wpm,
            layout_error_rate=self.layout_error_rate,
            paste_threshold=threshold,
            paste_delay_before=self.paste_delay_before,
            paste_delay_after=self.paste_delay_after,
        )

    def click(
        self,
        driver: Any,
        selector: str | None = None,
        x: int | None = None,
        y: int | None = None,
        start: tuple[int, int] | None = None,
        algorithm: str = "windmouse",
    ) -> None:
        """Синхронно выполняет клик через Selenium с биометрией удержания кнопки мыши.

        Args:
            driver: Экземпляр Selenium WebDriver.
            selector: Селектор целевого элемента.
            x: Координата X клика.
            y: Координата Y клика.
            start: Начальные координаты мыши.
            algorithm: Алгоритм перемещения ('windmouse' или 'bezier').
        """
        click(
            driver=driver,
            selector=selector,
            x=x,
            y=y,
            start=start,
            algorithm=algorithm,
            hold_time=self.click_hold_time,
        )
