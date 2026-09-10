"""Тесты для улучшенного антидетекта и фабрики Camoufox."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
from chutils.scraping.camoufox import launch_camoufox
from chutils.scraping.humanize.antidetect import (
    _get_antidetect_js,
    get_client_hints,
)


def test_antidetect_deterministic_canvas_seed() -> None:
    """Скрипт антидетекта использует детерминированный сид, а не Math.random."""
    js_default = _get_antidetect_js(
        "Vendor", "Renderer", 8, 8, session_seed="sess_abc123"
    )
    assert "Math.random" not in js_default
    # Проверяем наличие LCG/детерминированного алгоритма шума
    assert "sess_abc123" in js_default or "hash" in js_default or "seed" in js_default


def test_antidetect_cross_realm_iframe_protection() -> None:
    """Скрипт антидетекта защищает от извлечения прототипов через скрытый iframe."""
    js = _get_antidetect_js("Vendor", "Renderer", 8, 8)
    assert "contentWindow" in js or "HTMLIFrameElement" in js
    assert "Function.prototype.toString" in js or "makeNative" in js


def test_get_client_hints_chrome_windows() -> None:
    """get_client_hints генерирует согласованные Client Hints для Windows Chrome."""
    hints = get_client_hints(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    assert hints["platform"] == "Windows"
    assert hints["mobile"] is False
    assert any(b["brand"] == "Google Chrome" for b in hints["brands"])
    assert any(b["version"] == "120" for b in hints["brands"])


def test_get_client_hints_macos_safari() -> None:
    """get_client_hints генерирует Client Hints для macOS."""
    hints = get_client_hints(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    )
    assert hints["platform"] == "macOS"
    assert hints["mobile"] is False


@pytest.mark.asyncio
async def test_launch_camoufox_missing_dependency() -> None:
    """launch_camoufox выбрасывает OptionalDependencyError если camoufox не установлен."""
    with patch("chutils.scraping.camoufox.CAMOUFOX_AVAILABLE", False):
        with pytest.raises(OptionalDependencyError) as exc_info:
            await launch_camoufox(headless=True)
        assert "camoufox" in str(exc_info.value)


@pytest.mark.asyncio
async def test_launch_camoufox_mocked_success() -> None:
    """launch_camoufox успешно запускает AsyncCamoufox при наличии библиотеки."""
    mock_browser = MagicMock()
    mock_camoufox_cls = MagicMock()
    mock_camoufox_cls.return_value.__aenter__ = AsyncMock(return_value=mock_browser)
    mock_camoufox_cls.return_value.__aexit__ = AsyncMock()

    with (
        patch("chutils.scraping.camoufox.CAMOUFOX_AVAILABLE", True),
        patch(
            "chutils.scraping.camoufox.get_async_camoufox_class",
            return_value=mock_camoufox_cls,
        ),
    ):
        async with await launch_camoufox(headless=True, os="windows") as browser:
            assert browser is mock_browser
            mock_camoufox_cls.assert_called_once_with(headless=True, os="windows")


def test_antidetect_web_worker_protection() -> None:
    """Скрипт антидетекта перехватывает window.Worker и внедряет преамбулу очистки webdriver."""
    js = _get_antidetect_js("Vendor", "Renderer", 8, 8)
    assert "window.Worker" in js or "Worker" in js
    assert "Blob" in js or "createObjectURL" in js
    assert "navigator.webdriver" in js


def test_antidetect_v8_stack_trace_cloaking() -> None:
    """makeNative маскирует stack trace при вызове ошибок внутри пропатченных функций."""
    js = _get_antidetect_js("Vendor", "Renderer", 8, 8)
    assert "stack" in js or "prepareStackTrace" in js or "Error.captureStackTrace" in js
