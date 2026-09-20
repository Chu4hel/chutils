from unittest.mock import AsyncMock, patch

import pytest

from chutils.scraping.humanize import (
    AntidetectConfig,
    BehavioralProfile,
    KeyboardTypoGenerator,
    WindMouseGenerator,
)


def test_behavioral_profile_public_export() -> None:
    """Проверяет экспорт BehavioralProfile напрямую из chutils."""
    import chutils

    assert hasattr(chutils, "BehavioralProfile")
    assert chutils.BehavioralProfile is BehavioralProfile


def test_behavioral_profile_from_seed_deterministic() -> None:
    """Проверяет, что один и тот же сид детерминированно создает одинаковый профиль."""
    p1 = BehavioralProfile.from_seed("user_session_42")
    p2 = BehavioralProfile.from_seed("user_session_42")
    p3 = BehavioralProfile.from_seed("different_seed")
    p4 = BehavioralProfile.from_seed(1337)

    assert p1 == p2
    assert p1.speed_wpm == p2.speed_wpm
    assert p1.typo_rate == p2.typo_rate
    assert p1.gravity == p2.gravity
    assert p1.wind == p2.wind
    assert p1.max_step == p2.max_step
    assert p1.key_hold_time == p2.key_hold_time
    assert p1.click_hold_time == p2.click_hold_time

    # Разные сиды дают разные профили
    assert p1 != p3
    assert p1.speed_wpm != p3.speed_wpm or p1.gravity != p3.gravity
    assert p4.seed == 1337


def test_behavioral_profile_ranges_and_aliases() -> None:
    """Проверяет допустимые диапазоны значений и свойства-алиасы."""
    profile = BehavioralProfile.from_seed("test_seed")

    # WPM
    assert 20.0 <= profile.speed_wpm <= 120.0
    assert profile.wpm == profile.speed_wpm

    # Typo rate
    assert 0.0 <= profile.typo_rate <= 0.15
    assert profile.error_rate == profile.typo_rate

    # WindMouse
    assert 5.0 <= profile.gravity <= 20.0
    assert 1.0 <= profile.wind <= 10.0
    assert 5.0 <= profile.max_step <= 30.0

    # Hold times
    k_min, k_max = profile.key_hold_time
    assert 0.01 <= k_min < k_max <= 0.2

    c_min, c_max = profile.click_hold_time
    assert 0.01 <= c_min < c_max <= 0.3


def test_behavioral_profile_create_generators() -> None:
    """Проверяет фабричные методы создания генераторов траекторий и опечаток."""
    profile = BehavioralProfile.from_seed(42)

    wind_mouse = profile.create_wind_mouse()
    assert isinstance(wind_mouse, WindMouseGenerator)
    assert wind_mouse.gravity == profile.gravity
    assert wind_mouse.wind == profile.wind
    assert wind_mouse.max_step == profile.max_step

    typo_gen = profile.create_typo_generator()
    assert isinstance(typo_gen, KeyboardTypoGenerator)
    assert typo_gen.layout_error_rate == profile.layout_error_rate
    assert typo_gen.delayed_fix_rate == profile.delayed_fix_rate


@pytest.mark.asyncio
async def test_behavioral_profile_async_actions() -> None:
    """Проверяет вызовы async_type_text и async_click через профиль."""
    profile = BehavioralProfile(
        speed_wpm=55.0,
        typo_rate=0.04,
        key_hold_time=(0.04, 0.08),
        click_hold_time=(0.06, 0.11),
        layout_error_rate=0.02,
        delayed_fix_rate=0.015,
    )

    page_mock = AsyncMock()

    with patch("chutils.scraping.humanize.behavior.async_type_text") as mock_type:
        await profile.async_type_text(page_mock, "#input", "Тест")
        mock_type.assert_called_once_with(
            page=page_mock,
            selector="#input",
            text="Тест",
            error_rate=profile.typo_rate,
            speed_wpm=profile.speed_wpm,
            key_hold_time=profile.key_hold_time,
            layout_error_rate=profile.layout_error_rate,
            delayed_fix_rate=profile.delayed_fix_rate,
            paste_threshold=profile.paste_threshold,
            paste_delay_before=profile.paste_delay_before,
            paste_delay_after=profile.paste_delay_after,
        )

        await profile.async_type_text(page_mock, "#input", "Тест", paste_threshold=20)
        assert mock_type.call_args.kwargs["paste_threshold"] == 20

    with patch("chutils.scraping.humanize.behavior.async_click") as mock_click:
        await profile.async_click(page_mock, selector="#btn")
        mock_click.assert_called_once_with(
            page=page_mock,
            selector="#btn",
            x=None,
            y=None,
            start=None,
            button="left",
            hold_time=profile.click_hold_time,
        )


def test_antidetect_config_integration() -> None:
    """Проверяет получение биометрического профиля из AntidetectConfig."""
    cfg = AntidetectConfig(session_seed="session_abc")
    profile = cfg.get_behavioral_profile()

    assert isinstance(profile, BehavioralProfile)
    assert profile.seed == "session_abc"

    # Повторный вызов с тем же сидом дает идентичный профиль
    profile2 = cfg.get_behavioral_profile()
    assert profile == profile2
