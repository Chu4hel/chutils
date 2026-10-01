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


