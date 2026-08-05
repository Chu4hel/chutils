from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from chutils.plugins import PluginError, PluginRegistry, register_plugin, registry


class DummyPlugin:
    def __init__(self, name: str = "dummy"):
        self.name = name


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Очищает реестр перед каждым тестом."""
    registry.clear()
    yield
    registry.clear()


def test_explicit_registration():
    """Проверяет явную регистрацию плагинов."""
    plugin = DummyPlugin("test-plugin")
    register_plugin(plugin)

    assert registry.get_plugin("test-plugin") is plugin
    assert plugin in registry.get_all_plugins()


def test_registration_missing_name():
    """Проверяет, что регистрация плагина без имени вызывает ошибку."""

    class BadPlugin:
        pass

    plugin = BadPlugin()
    with pytest.raises(PluginError, match="атрибут 'name'"):
        register_plugin(plugin)


def test_get_plugins_by_type():
    """Проверяет фильтрацию плагинов по базовому классу/интерфейсу."""

    class BaseInterface:
        name = "base"

    class DerivedPlugin(BaseInterface):
        name = "derived"

    class UnrelatedPlugin:
        name = "unrelated"

    derived = DerivedPlugin()
    unrelated = UnrelatedPlugin()

    register_plugin(derived)
    register_plugin(unrelated)

    matching = registry.get_plugins_by_type(BaseInterface)
    assert derived in matching
    assert unrelated not in matching


def test_plugin_registry_singleton():
    """Проверяет, что PluginRegistry является синглтоном."""
    reg1 = PluginRegistry()
    reg2 = PluginRegistry()
    assert reg1 is reg2


@patch("importlib.metadata.entry_points")
def test_discover_plugins_success(mock_entry_points):
    """Проверяет автообнаружение плагинов через entry_points."""
    mock_ep = MagicMock()
    mock_ep.name = "mock_plugin"
    mock_ep.value = "mock_module:MockPlugin"

    # Возвращаем наш мок-класс при ep.load()
    class MockPlugin:
        name = "discovered_plugin"

    mock_ep.load.return_value = MockPlugin

    # Настраиваем возвращаемое значение entry_points
    mock_entry_points.return_value = [mock_ep]

    registry.discover_plugins("chutils.plugins.test")

    plugin = registry.get_plugin("discovered_plugin")
    assert plugin is not None
    assert isinstance(plugin, MockPlugin)


@patch("importlib.metadata.entry_points")
def test_discover_plugins_isolation(mock_entry_points):
    """Проверяет, что ошибка при импорте одного плагина не ломает автообнаружение остальных."""
    mock_faulty_ep = MagicMock()
    mock_faulty_ep.name = "faulty"
    mock_faulty_ep.value = "faulty_module:Faulty"
    mock_faulty_ep.load.side_effect = ImportError("No module named faulty_dependency")

    mock_valid_ep = MagicMock()
    mock_valid_ep.name = "valid"
    mock_valid_ep.value = "valid_module:Valid"

    class ValidPlugin:
        name = "valid_plugin"

    mock_valid_ep.load.return_value = ValidPlugin

    mock_entry_points.return_value = [mock_faulty_ep, mock_valid_ep]

    # Запуск автообнаружения не должен вызывать исключений наружу
    registry.discover_plugins("chutils.plugins.test_isolation")

    # Неисправный плагин не должен быть зарегистрирован, но исправный должен
    assert registry.get_plugin("valid_plugin") is not None
    assert isinstance(registry.get_plugin("valid_plugin"), ValidPlugin)


def test_captcha_solver_plugin_registration():
    """Проверяет регистрацию и получение плагина CaptchaSolverPlugin."""
    from chutils.plugins import CaptchaSolverPlugin
    from chutils.plugins.core import get_captcha_solver_plugin

    class MyCaptchaSolver(CaptchaSolverPlugin):
        name = "my_custom_captcha"

        def solve_recaptcha(self, sitekey: str, page_url: str, timeout: float = 120.0, poll_interval: float = 5.0, **kwargs) -> str:
            return "mocked-g-recaptcha-response"

    solver = MyCaptchaSolver()
    register_plugin(solver)

    found = get_captcha_solver_plugin("my_custom_captcha")
    assert found is solver
    assert found.solve_recaptcha("sitekey", "http://example.com") == "mocked-g-recaptcha-response"


def test_task_queue_plugin_registration():
    """Проверяет регистрацию и получение плагина TaskQueuePlugin."""
    from chutils.plugins import TaskQueuePlugin
    from chutils.plugins.core import get_task_queue_plugin

    class MyRabbitMQTaskQueuePlugin(TaskQueuePlugin):
        name = "rabbitmq_queue"

        def create_queue(self, name: str, **kwargs):
            return f"Queue({name})"

    plugin = MyRabbitMQTaskQueuePlugin()
    register_plugin(plugin)

    found = get_task_queue_plugin("rabbitmq_queue")
    assert found is plugin
    assert found.create_queue("scrapes") == "Queue(scrapes)"
