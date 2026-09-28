"""Unit-тесты для мобильных пресетов AntidetectConfig и сенсорных скриптов."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chutils.scraping.humanize import (
    AntidetectConfig,
    apply_antidetect_nodriver,
    apply_antidetect_selenium,
)


def test_preset_mobile_android_defaults() -> None:
    """Проверка пресета Android Pixel 8 по умолчанию."""
    config = AntidetectConfig.preset_mobile_android()

    assert config.is_mobile is True
    assert config.has_touch is True
    assert config.max_touch_points == 5
    assert config.is_ios is False

    assert "Android" in (config.user_agent or "")
    assert "Pixel 8" in (config.user_agent or "")
    assert "Chrome" in (config.user_agent or "")

    assert config.screen_width == 412
    assert config.screen_height == 915
    assert config.device_pixel_ratio == 2.625

    assert config.client_hints is not None
    assert config.client_hints["platform"] == "Android"
    assert config.client_hints["mobile"] is True

    assert config.orientation is not None
    assert config.orientation["type"] == "portrait-primary"
    assert config.orientation["angle"] == 0

    assert config.hardware_concurrency == 8
    assert config.device_memory == 8


def test_preset_mobile_android_custom_device() -> None:
    """Проверка пресета Android с кастомными моделями устройств."""
    pixel7 = AntidetectConfig.preset_mobile_android(device="pixel_7")
    assert "Pixel 7" in (pixel7.user_agent or "")

    galaxy = AntidetectConfig.preset_mobile_android(device="galaxy_s24")
    assert "SM-S921" in (galaxy.user_agent or "")
    assert galaxy.screen_width == 360
    assert galaxy.screen_height == 780
    assert galaxy.device_pixel_ratio == 3.0


def test_preset_mobile_ios_defaults() -> None:
    """Проверка пресета iOS Safari по умолчанию (iPhone 15)."""
    config = AntidetectConfig.preset_mobile_ios()

    assert config.is_mobile is True
    assert config.has_touch is True
    assert config.max_touch_points == 5
    assert config.is_ios is True

    assert "iPhone" in (config.user_agent or "")
    assert "Safari" in (config.user_agent or "")
    assert "Version/17" in (config.user_agent or "")

    assert config.screen_width == 393
    assert config.screen_height == 852
    assert config.device_pixel_ratio == 3.0

    assert config.client_hints is not None
    assert config.client_hints["platform"] == "iOS"
    assert config.client_hints["mobile"] is True

    assert "Apple" in config.webgl_vendor
    assert "Apple" in config.webgl_renderer


def test_preset_mobile_ios_custom_device() -> None:
    """Проверка пресета iOS с кастомным устройством iPhone 14."""
    iphone14 = AntidetectConfig.preset_mobile_ios(device="iphone_14")
    assert "iPhone" in (iphone14.user_agent or "")
    assert iphone14.screen_width == 390
    assert iphone14.screen_height == 844
    assert iphone14.device_pixel_ratio == 3.0


def test_mobile_init_script_generation() -> None:
    """Проверка генерации JS-скрипта для мобильного устройства."""
    android_config = AntidetectConfig.preset_mobile_android()
    js = android_config.get_init_script()

    # Проверка Touch API
    assert "maxTouchPoints" in js
    assert "TouchEvent" in js
    assert "ontouchstart" in js

    # Проверка DeviceMotion и DeviceOrientation
    assert "DeviceMotionEvent" in js
    assert "DeviceOrientationEvent" in js
    assert "portrait-primary" in js

    # Проверка отсутствия iOS компонентов в Android
    assert "ApplePaySession" not in js

    # Проверка скрипта для iOS
    ios_config = AntidetectConfig.preset_mobile_ios()
    ios_js = ios_config.get_init_script()
    assert "window.safari" in ios_js
    assert "ApplePaySession" in ios_js


@pytest.mark.asyncio
async def test_apply_antidetect_nodriver_mobile() -> None:
    """Проверка вызова CDP-методов эмуляции устройства и тач-событий в nodriver."""
    fake_tab = MagicMock()
    fake_tab.send = AsyncMock()
    fake_tab.evaluate = AsyncMock()

    config = AntidetectConfig.preset_mobile_android()

    # Мокаем nodriver и cdp модули
    mock_nodriver = MagicMock()
    mock_cdp = MagicMock()
    mock_emulation = MagicMock()
    mock_page = MagicMock()

    mock_cdp.emulation = mock_emulation
    mock_cdp.page = mock_page
    mock_nodriver.cdp = mock_cdp

    import sys
    sys.modules["nodriver"] = mock_nodriver
    sys.modules["nodriver.cdp"] = mock_cdp
    sys.modules["nodriver.cdp.emulation"] = mock_emulation
    sys.modules["nodriver.cdp.page"] = mock_page

    try:
        await apply_antidetect_nodriver(fake_tab, config=config)

        # Проверяем что mobile=True передано в set_device_metrics_override
        mock_emulation.set_device_metrics_override.assert_called_once()
        _, kwargs = mock_emulation.set_device_metrics_override.call_args
        assert kwargs.get("mobile") is True
        assert kwargs.get("width") == 412
        assert kwargs.get("height") == 915
        assert kwargs.get("device_scale_factor") == 2.625

        # Проверяем включение тач-эмуляции
        mock_emulation.set_touch_emulation_enabled.assert_called_once_with(enabled=True, max_touch_points=5)
    finally:
        sys.modules.pop("nodriver", None)
        sys.modules.pop("nodriver.cdp", None)
        sys.modules.pop("nodriver.cdp.emulation", None)
        sys.modules.pop("nodriver.cdp.page", None)


def test_apply_antidetect_selenium_mobile() -> None:
    """Проверка передачи mobile=True в CDP для Selenium."""
    driver = MagicMock()
    driver.execute_cdp_cmd = MagicMock()

    config = AntidetectConfig.preset_mobile_android()

    apply_antidetect_selenium(driver, config=config)

    # Ищем вызовы Emulation.setDeviceMetricsOverride и Emulation.setTouchEmulationEnabled
    calls = driver.execute_cdp_cmd.call_args_list
    cmd_names = [call[0][0] for call in calls]

    assert "Emulation.setDeviceMetricsOverride" in cmd_names
    metrics_call = next(c for c in calls if c[0][0] == "Emulation.setDeviceMetricsOverride")
    assert metrics_call[0][1]["mobile"] is True
    assert metrics_call[0][1]["width"] == 412

    assert "Emulation.setTouchEmulationEnabled" in cmd_names
    touch_call = next(c for c in calls if c[0][0] == "Emulation.setTouchEmulationEnabled")
    assert touch_call[0][1]["enabled"] is True
    assert touch_call[0][1]["maxTouchPoints"] == 5
