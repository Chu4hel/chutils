"""Тестирование экспорта нового публичного API версии 4.0.0."""

from __future__ import annotations

import chutils


def test_public_api_captcha_exports() -> None:
    """Проверяет экспорт новых классов и моделей капч из корня chutils."""
    from chutils import (
        AsyncGeeTestSolver,
        AsyncReCaptchaEnterpriseSolver,
        GeeTestResult,
        GeeTestSolver,
        GeeTestTaskConfig,
        ReCaptchaEnterpriseConfig,
        ReCaptchaEnterpriseSolver,
    )

    assert GeeTestSolver is not None
    assert AsyncGeeTestSolver is not None
    assert ReCaptchaEnterpriseSolver is not None
    assert AsyncReCaptchaEnterpriseSolver is not None
    assert GeeTestResult is not None
    assert GeeTestTaskConfig is not None
    assert ReCaptchaEnterpriseConfig is not None

    assert "GeeTestSolver" in chutils.__all__
    assert "ReCaptchaEnterpriseSolver" in chutils.__all__


def test_public_api_touch_exports() -> None:
    """Проверяет экспорт сенсорных генераторов и функций из корня chutils."""
    from chutils import (
        TouchGestureGenerator,
        TouchPoint,
        async_touch_swipe,
        async_touch_tap,
    )

    assert TouchGestureGenerator is not None
    assert TouchPoint is not None
    assert callable(async_touch_tap)
    assert callable(async_touch_swipe)

    assert "TouchGestureGenerator" in chutils.__all__
    assert "TouchPoint" in chutils.__all__
    assert "async_touch_tap" in chutils.__all__
    assert "async_touch_swipe" in chutils.__all__


def test_public_api_bidi_exports() -> None:
    """Проверяет экспорт WebDriver BiDi классов, исключений и функций из корня chutils."""
    from chutils import (
        BiDiClient,
        BiDiCommandError,
        BiDiConnectionError,
        BiDiError,
        BiDiSession,
        BiDiTimeoutError,
        apply_antidetect_bidi,
        bidi_session,
        extract_bidi_url,
    )

    assert BiDiClient is not None
    assert BiDiSession is not None
    assert callable(bidi_session)
    assert callable(apply_antidetect_bidi)
    assert callable(extract_bidi_url)
    assert issubclass(BiDiConnectionError, BiDiError)
    assert issubclass(BiDiCommandError, BiDiError)
    assert issubclass(BiDiTimeoutError, BiDiError)

    assert "BiDiClient" in chutils.__all__
    assert "BiDiSession" in chutils.__all__
    assert "bidi_session" in chutils.__all__
    assert "apply_antidetect_bidi" in chutils.__all__
