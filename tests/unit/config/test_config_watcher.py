import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from chutils.config import (
    get_config,
    _cm,
    on_config_change,
    start_config_watcher,
    stop_config_watcher
)
from chutils.config.watcher import ConfigChangeHandler
from chutils.exceptions import OptionalDependencyError


def test_graceful_degradation_no_watchdog(monkeypatch):
    """Тест: start_config_watcher бросает OptionalDependencyError, если watchdog не установлен."""
    # Эмулируем отсутствие watchdog через централизованный флаг
    monkeypatch.setattr("chutils.env.WATCHDOG_AVAILABLE", False)

    with pytest.raises(OptionalDependencyError) as excinfo:
        start_config_watcher()
    assert "watchdog" in str(excinfo.value).lower()


def test_callback_registration():
    """Тест регистрации и вызова коллбеков."""
    _cm._reset()
    mock_callback = MagicMock()
    on_config_change(mock_callback)

    assert mock_callback in _cm.get_callbacks()

    # Вызываем коллбеки напрямую через менеджер
    for cb in _cm.get_callbacks():
        cb()
    mock_callback.assert_called_once()


def test_debounce_logic(mocker):
    """Тест механизма debounce: несколько быстрых событий -> один вызов."""
    _cm._reset()
    mock_callback = MagicMock()
    on_config_change(mock_callback)

    handler = ConfigChangeHandler(["/tmp/config.yml"])

    # Первое срабатывание
    handler._on_modified()
    mock_callback.assert_called_once()

    # Быстрое второе срабатывание (должно игнорироваться)
    handler._on_modified()
    mock_callback.assert_called_once()  # Все еще один раз

    # Имитируем прошествие времени
    _cm.last_reload_time -= 2.0
    handler._on_modified()
    assert mock_callback.call_count == 2


@pytest.mark.usefixtures("fs")
def test_integration_reload(fs, mocker):
    """Интеграционный тест: изменение файла -> сброс кэша и вызов коллбека."""
    _cm._reset()

    # Создаем фиктивный конфиг
    config_path = "/app/config.yml"
    fs.create_file(config_path, contents="test: value1")

    _cm.config_file_path = config_path
    _cm.paths_initialized = True

    mock_callback = MagicMock()
    on_config_change(mock_callback)

    # Загружаем конфиг
    assert get_config()["test"] == "value1"
    assert _cm.config_loaded is True

    # Имитируем работу watchdog через хендлер
    handler = ConfigChangeHandler([config_path])

    # Меняем файл на диске
    Path(config_path).write_text("test: value2", encoding="utf-8")

    # Вызываем хендлер
    handler._on_modified()

    mock_callback.assert_called_once()
    assert _cm.config_loaded is False
    assert _cm.config_object is None

    # Проверяем, что подхватилось новое значение
    assert get_config()["test"] == "value2"


def test_start_stop_watcher(mocker):
    """Тест запуска и остановки watcher'а."""
    _cm._reset()
    _cm.config_file_path = "/tmp/config.yml"
    _cm.paths_initialized = True

    # Мокаем Observer
    mock_observer_cls = mocker.patch("watchdog.observers.Observer")
    mock_observer = mock_observer_cls.return_value

    # Мокаем существование файла
    mocker.patch("pathlib.Path.exists", return_value=True)

    start_config_watcher()
    assert _cm.observer is not None
    mock_observer.start.assert_called_once()

    stop_config_watcher()
    assert _cm.observer is None
    mock_observer.stop.assert_called_once()
    mock_observer.join.assert_called_once()


def test_internal_save_suppression(mocker):
    """Тест: save_config_value(notify=False) подавляет Hot-Reload коллбэк."""
    _cm._reset()
    config_path = "/tmp/config.yml"
    _cm.config_file_path = config_path
    _cm.paths_initialized = True

    mock_callback = MagicMock()
    on_config_change(mock_callback)

    # Мокаем провайдер сохранения
    mock_provider = MagicMock()
    mock_provider.save.return_value = True
    mocker.patch("chutils.config.utils._PROVIDERS", {".yml": mock_provider})

    from chutils.config import save_config_value
    from chutils.config.watcher import ConfigChangeHandler
    handler = ConfigChangeHandler([config_path])

    # 1. Сохраняем с notify=False
    save_config_value("Section", "Key", "Value", notify=False)

    # Имитируем событие от ОС
    handler._on_modified()

    # Коллбэк НЕ должен быть вызван
    mock_callback.assert_not_called()

    # 2. Сохраняем с notify=True (по умолчанию)
    save_config_value("Section", "Key", "Value2", notify=True)

    # Имитируем событие от ОС
    handler._on_modified()

    # Коллбэк ДОЛЖЕН быть вызван
    mock_callback.assert_called_once()
