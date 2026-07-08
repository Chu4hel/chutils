from unittest.mock import patch
import pytest


def test_scraping_imports_without_playwright_and_selenium() -> None:
    """Проверяет, что базовый модуль импортируется корректно без playwright/selenium."""
    with patch("importlib.util.find_spec", return_value=None):
        import chutils.scraping.humanize as humanize
        assert humanize.async_move_mouse is not None
        assert humanize.move_mouse is not None


def test_playwright_functions_raise_dependency_error_when_missing() -> None:
    """Проверяет выброс ошибки при вызове playwright-функций без установленной библиотеки."""
    from chutils.exceptions import OptionalDependencyError

    with patch("importlib.util.find_spec", return_value=None):
        import chutils.scraping.humanize as humanize

        with pytest.raises(OptionalDependencyError) as exc_info:
            import asyncio
            asyncio.run(humanize.async_move_mouse(None, 0, 0))

        assert "playwright" in str(exc_info.value)
        assert exc_info.value.context.get("dependency") == "playwright"


def test_selenium_functions_raise_dependency_error_when_missing() -> None:
    """Проверяет выброс ошибки при вызове selenium-функций без установленной библиотеки."""
    from chutils.exceptions import OptionalDependencyError

    with patch("importlib.util.find_spec", return_value=None):
        import chutils.scraping.humanize as humanize

        with pytest.raises(OptionalDependencyError) as exc_info:
            humanize.move_mouse(None, 0, 0)

        assert "selenium" in str(exc_info.value)
        assert exc_info.value.context.get("dependency") == "selenium"
