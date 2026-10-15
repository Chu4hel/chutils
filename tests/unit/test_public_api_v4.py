"""Тестирование экспорта нового публичного API версии 4.0.0."""

from __future__ import annotations

import pytest

import chutils


def test_public_api_captcha_removed() -> None:
    """Проверяет, что решатели капч вынесены из chutils в pycaptcha-hub."""
    assert "captcha" not in chutils.__all__
    assert "GeeTestSolver" not in chutils.__all__
    assert "ReCaptchaEnterpriseSolver" not in chutils.__all__
    assert "RuCaptchaSolver" not in chutils.__all__

    with pytest.raises(AttributeError):
        _ = chutils.GeeTestSolver
