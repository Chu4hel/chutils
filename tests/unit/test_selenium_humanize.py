import importlib.util
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from chutils.scraping.humanize.actions import (
    move_mouse,
    scroll_to,
    type_text,
)

mock_action_chains_class = MagicMock()
mock_action_chains_class.__spec__ = MagicMock()

mock_keys = MagicMock()
mock_keys.BACKSPACE = "\ue003"
mock_keys.__spec__ = MagicMock()

mock_by = MagicMock()
mock_by.CSS_SELECTOR = "css selector"
mock_by.__spec__ = MagicMock()


@pytest.fixture(autouse=True)
def mock_selenium_modules(mocker: MockerFixture) -> None:
    """Глобально подменяет модули selenium для всех тестов в файле."""
    # Создаем моки модулей и прописываем им __spec__ во избежание ValueError: selenium.__spec__ is not set
    mock_sel = MagicMock()
    mock_sel.__spec__ = MagicMock()

    mock_webdriver = MagicMock()
    mock_webdriver.__spec__ = MagicMock()

    mock_common = MagicMock()
    mock_common.__spec__ = MagicMock()

    mocker.patch.dict(
        "sys.modules",
        {
            "selenium": mock_sel,
            "selenium.webdriver": mock_webdriver,
            "selenium.webdriver.common": mock_common,
            "selenium.webdriver.common.action_chains": mock_action_chains_class,
            "selenium.webdriver.common.keys": mock_keys,
            "selenium.webdriver.common.by": mock_by,
        },
    )

    # Патчим find_spec, чтобы он возвращал фиктивный spec для selenium
    orig_find_spec = importlib.util.find_spec

    def custom_find_spec(name: str, package: str | None = None) -> Any:
        if name == "selenium":
            mock_spec = MagicMock()
            mock_spec.__spec__ = MagicMock()
            return mock_spec
        return orig_find_spec(name, package)

    mocker.patch("importlib.util.find_spec", side_effect=custom_find_spec)


def test_move_mouse() -> None:
    """Проверяет плавное перемещение мыши в Selenium."""
    driver = MagicMock()
    mock_action_chains = MagicMock()
    mock_action_chains_class.ActionChains.return_value = mock_action_chains
    mock_action_chains.move_by_offset.return_value = mock_action_chains

    move_mouse(driver, x=150, y=200, start=(0, 0), steps=10, delay_between_steps=0.001)

    assert mock_action_chains_class.ActionChains.call_count == 10
    assert mock_action_chains.move_by_offset.call_count == 10
    assert mock_action_chains.perform.call_count == 10


def test_scroll_to() -> None:
    """Проверяет имитацию скроллинга в Selenium."""
    driver = MagicMock()
    driver.execute_script.return_value = 0

    scroll_to(driver, x=0, y=300, steps=10, delay_between_steps=0.001)

    assert driver.execute_script.call_count > 2

    last_call = driver.execute_script.call_args_list[-1][0][0]
    assert "scrollTo" in last_call
    assert "300" in last_call


def test_type_text() -> None:
    """Проверяет имитацию ввода текста в Selenium."""
    driver = MagicMock()
    element = MagicMock()
    driver.find_element.return_value = element

    type_text(driver, selector="#input", text="hello", error_rate=0.0, speed_wpm=300.0)

    driver.find_element.assert_called_once()
    element.click.assert_called_once()
    assert element.send_keys.call_count == 5
