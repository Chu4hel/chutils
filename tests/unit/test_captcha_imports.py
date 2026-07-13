from unittest.mock import patch

import pytest


def test_captcha_imports_without_httpx() -> None:
    """Проверяет, что базовый модуль импортируется корректно без httpx."""
    with patch("importlib.util.find_spec", return_value=None):
        import chutils.scraping.captcha as captcha
        assert captcha is not None


def test_captcha_solver_raises_dependency_error_when_missing_httpx() -> None:
    """Проверяет выброс OptionalDependencyError при обращении к клиенту без httpx."""
    from chutils.exceptions import OptionalDependencyError
    with patch("importlib.util.find_spec", return_value=None):
        import chutils.scraping.captcha as captcha
        with pytest.raises(OptionalDependencyError) as exc_info:
            captcha.RuCaptchaSolver(api_key="test")

        assert "httpx" in str(exc_info.value)
        assert exc_info.value.context.get("dependency") == "httpx"
