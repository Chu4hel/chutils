"""Unit-тесты для AntidetectConfig и безопасных дефолтов антидетекта."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from chutils.scraping.humanize import (
    AntidetectConfig,
    apply_antidetect_nodriver,
    apply_antidetect_playwright,
    apply_antidetect_selenium,
)


def test_antidetect_config_defaults() -> None:
    """Проверка значений по умолчанию AntidetectConfig."""
    cfg = AntidetectConfig()
    assert cfg.stealth_minimal is True
    assert cfg.hardware_concurrency == 8
    assert cfg.device_memory == 8
    assert cfg.session_seed == 1337
    assert cfg.client_hints is None
    assert "NVIDIA" in cfg.webgl_vendor


def test_antidetect_config_validation() -> None:
    """Проверка валидации числовых диапазонов AntidetectConfig."""
    with pytest.raises(ValidationError):
        AntidetectConfig(hardware_concurrency=0)

    with pytest.raises(ValidationError):
        AntidetectConfig(device_memory=-1)


def test_antidetect_config_presets() -> None:
    """Проверка фабричных методов пресетов."""
    stealth = AntidetectConfig.preset_stealth_nodriver(session_seed="seed1")
    assert stealth.stealth_minimal is True
    assert stealth.session_seed == "seed1"

    aggressive = AntidetectConfig.preset_aggressive(session_seed="seed2")
    assert aggressive.stealth_minimal is False
    assert aggressive.session_seed == "seed2"

    minimal = AntidetectConfig.preset_minimal()
    assert minimal.stealth_minimal is True


def test_antidetect_config_get_init_script() -> None:
    """Проверка генерации JS через get_init_script()."""
    cfg_stealth = AntidetectConfig(stealth_minimal=True)
    script_stealth = cfg_stealth.get_init_script()
    assert "const isMinimal = true;" in script_stealth

    cfg_aggr = AntidetectConfig(stealth_minimal=False)
    script_aggr = cfg_aggr.get_init_script()
    assert "const isMinimal = false;" in script_aggr


@pytest.mark.asyncio
async def test_apply_antidetect_nodriver_defaults() -> None:
    """Проверка того, что по умолчанию apply_antidetect_nodriver использует stealth_minimal=True."""
    mock_nodriver = MagicMock()
    mock_cdp = MagicMock()
    mock_page = MagicMock()
    mock_cdp.page = mock_page
    mock_nodriver.cdp = mock_cdp

    mock_tab = MagicMock()
    mock_tab.send = AsyncMock()

    sys.modules["nodriver"] = mock_nodriver
    sys.modules["nodriver.cdp"] = mock_cdp
    sys.modules["nodriver.cdp.page"] = mock_page

    try:
        await apply_antidetect_nodriver(mock_tab)
        assert mock_tab.send.called
        # Проверяем аргумент команды add_script_to_evaluate_on_new_document
        call_args = mock_page.add_script_to_evaluate_on_new_document.call_args
        source_code = call_args.kwargs.get("source") or call_args.args[0]
        assert "const isMinimal = true;" in source_code
    finally:
        sys.modules.pop("nodriver", None)
        sys.modules.pop("nodriver.cdp", None)
        sys.modules.pop("nodriver.cdp.page", None)


@pytest.mark.asyncio
async def test_apply_antidetect_nodriver_with_config() -> None:
    """Проверка передачи AntidetectConfig в apply_antidetect_nodriver."""
    mock_nodriver = MagicMock()
    mock_cdp = MagicMock()
    mock_page = MagicMock()
    mock_cdp.page = mock_page
    mock_nodriver.cdp = mock_cdp

    mock_tab = MagicMock()
    mock_tab.send = AsyncMock()

    sys.modules["nodriver"] = mock_nodriver
    sys.modules["nodriver.cdp"] = mock_cdp
    sys.modules["nodriver.cdp.page"] = mock_page

    cfg = AntidetectConfig.preset_aggressive(hardware_concurrency=16)

    try:
        await apply_antidetect_nodriver(mock_tab, config=cfg)
        assert mock_tab.send.called
        call_args = mock_page.add_script_to_evaluate_on_new_document.call_args
        source_code = call_args.kwargs.get("source") or call_args.args[0]
        assert "const isMinimal = false;" in source_code
        assert "16" in source_code
    finally:
        sys.modules.pop("nodriver", None)
        sys.modules.pop("nodriver.cdp", None)
        sys.modules.pop("nodriver.cdp.page", None)


@pytest.mark.asyncio
async def test_config_apply_to_engines() -> None:
    """Проверка методов apply_to_playwright, apply_to_selenium и apply_to_nodriver модели AntidetectConfig."""
    cfg = AntidetectConfig(stealth_minimal=False, hardware_concurrency=4)

    # Playwright
    mock_playwright = MagicMock()
    mock_context = MagicMock()
    mock_context.add_init_script = AsyncMock()
    sys.modules["playwright"] = mock_playwright
    try:
        await cfg.apply_to_playwright(mock_context)
        assert mock_context.add_init_script.called
        pw_script = mock_context.add_init_script.call_args.args[0]
        assert "const isMinimal = false;" in pw_script
    finally:
        sys.modules.pop("playwright", None)

    # Selenium
    mock_selenium = MagicMock()
    mock_driver = MagicMock()
    mock_driver.execute_cdp_cmd = MagicMock()
    sys.modules["selenium"] = mock_selenium
    try:
        cfg.apply_to_selenium(mock_driver)
        assert mock_driver.execute_cdp_cmd.called

        # Direct function calls
        apply_antidetect_selenium(mock_driver, config=cfg)
        assert mock_driver.execute_cdp_cmd.call_count == 2
    finally:
        sys.modules.pop("selenium", None)


@pytest.mark.asyncio
async def test_apply_antidetect_playwright_direct() -> None:
    """Проверка прямого вызова apply_antidetect_playwright с config."""
    mock_playwright = MagicMock()
    mock_context = MagicMock()
    mock_context.add_init_script = AsyncMock()
    sys.modules["playwright"] = mock_playwright
    cfg = AntidetectConfig.preset_minimal()
    try:
        await apply_antidetect_playwright(mock_context, config=cfg)
        assert mock_context.add_init_script.called
    finally:
        sys.modules.pop("playwright", None)


@pytest.mark.asyncio
async def test_apply_antidetect_nodriver_user_agent_override() -> None:
    """Проверка отправки команды emulation.set_user_agent_override при наличии user_agent."""
    mock_nodriver = MagicMock()
    mock_cdp = MagicMock()
    mock_page = MagicMock()
    mock_emulation = MagicMock()
    mock_cdp.page = mock_page
    mock_cdp.emulation = mock_emulation
    mock_nodriver.cdp = mock_cdp

    mock_tab = MagicMock()
    mock_tab.send = AsyncMock()

    sys.modules["nodriver"] = mock_nodriver
    sys.modules["nodriver.cdp"] = mock_cdp
    sys.modules["nodriver.cdp.page"] = mock_page
    sys.modules["nodriver.cdp.emulation"] = mock_emulation

    test_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TestBrowser/1.0"
    cfg = AntidetectConfig(user_agent=test_ua)

    try:
        await apply_antidetect_nodriver(mock_tab, config=cfg)
        assert mock_emulation.set_user_agent_override.called
        mock_emulation.set_user_agent_override.assert_called_once_with(
            user_agent=test_ua
        )
        assert mock_tab.send.called
    finally:
        sys.modules.pop("nodriver", None)
        sys.modules.pop("nodriver.cdp", None)
        sys.modules.pop("nodriver.cdp.page", None)
        sys.modules.pop("nodriver.cdp.emulation", None)


def test_fingerprint_profile_to_antidetect_config_user_agent() -> None:
    """Проверка проброса user_agent из FingerprintProfile в AntidetectConfig."""
    from chutils.scraping.fingerprint.models import FingerprintProfile

    profile = FingerprintProfile(user_agent="Custom-UA/2.0")
    config = profile.to_antidetect_config()

    assert config.user_agent == "Custom-UA/2.0"

