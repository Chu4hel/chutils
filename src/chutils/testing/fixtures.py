"""
Pytest-фикстуры для тестирования приложений, использующих chutils.
"""

import logging
from typing import Any, Dict, List, Optional

import pytest
from chutils.config.manager import _cm
from chutils.secret_manager.core import SecretManager
from chutils.secret_manager.providers import SecretProvider


class ConfigMock:
    """
    Вспомогательный класс для управления мокированной конфигурацией.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        _cm.set_config(self._data)

    def set(self, section: str, key: str, value: Any) -> None:
        """
        Устанавливает значение в мокированной конфигурации.
        """
        if section not in self._data:
            self._data[section] = {}
        self._data[section][key] = value
        # Обновляем кэш в синглтоне
        _cm.set_config(self._data)

    def load(self, data: Dict[str, Dict[str, Any]]) -> None:
        """
        Загружает весь словарь конфигурации целиком.
        """
        self._data.update(data)
        _cm.set_config(self._data)


class MockSecretProvider(SecretProvider):
    """
    Провайдер секретов для тестов, хранящий данные в памяти.
    """

    def __init__(self) -> None:
        self.secrets: Dict[str, str] = {}

    def get(self, key: str, service_name: str) -> Optional[str]:
        return self.secrets.get(key)

    def set(self, key: str, value: str, service_name: str) -> bool:
        self.secrets[key] = value
        return True

    def delete(self, key: str, service_name: str) -> bool:
        if key in self.secrets:
            del self.secrets[key]
            return True
        return False

    def set_secret(self, key: str, value: str) -> None:
        """
        Удобный метод для предустановки секрета в тестах.
        """
        self.secrets[key] = value


class LogCaptureHandler(logging.Handler):
    """
    Обработчик логов, сохраняющий записи в список для последующего анализа.
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class LogCapture:
    """
    Интерфейс для анализа перехваченных логов.
    """

    def __init__(self, handler: LogCaptureHandler) -> None:
        self._handler = handler

    @property
    def records(self) -> List[logging.LogRecord]:
        """Возвращает список всех перехваченных LogRecord."""
        return self._handler.records

    def messages(self) -> List[str]:
        """Возвращает список текстовых сообщений всех логов."""
        return [r.getMessage() for r in self.records]

    def has_message(self, text: str, partial: bool = True) -> bool:
        """
        Проверяет наличие сообщения в логах.

        Args:
            text: Искомый текст.
            partial: Если True, ищет подстроку. Если False, точное совпадение.
        """
        for msg in self.messages():
            if partial and text in msg:
                return True
            if not partial and text == msg:
                return True
        return False

    def get_by_field(self, field_name: str, value: Any) -> List[logging.LogRecord]:
        """
        Возвращает список записей, у которых указанное поле равно значению.
        Полезно для поиска по trace_id, user_id и другим полям контекста.
        """
        return [r for r in self.records if getattr(r, field_name, None) == value]

    def clear(self) -> None:
        """Очищает список перехваченных логов."""
        self._handler.records.clear()


@pytest.fixture
def mock_chutils_config(monkeypatch: pytest.MonkeyPatch) -> ConfigMock:
    """
    Фикстура для мокирования конфигурации chutils.

    - Отключает переопределение через переменные окружения (CH_DISABLE_ENV_OVERRIDE=true).
    - Сбрасывает состояние глобального ConfigManager до и после теста.
    - Возвращает объект с методом .set(section, key, value).
    """
    monkeypatch.setenv("CH_DISABLE_ENV_OVERRIDE", "true")
    _cm._reset()
    _cm.paths_initialized = True

    mock = ConfigMock()
    yield mock
    _cm._reset()


@pytest.fixture
def mock_chutils_secrets(monkeypatch: pytest.MonkeyPatch) -> MockSecretProvider:
    """
    Фикстура для мокирования секретов chutils.

    - Заменяет все провайдеры в SecretManager на один MockSecretProvider.
    - Отключает предупреждение о миграции keyring.
    """
    provider = MockSecretProvider()

    monkeypatch.setattr("chutils.secret_manager.core._warn_about_keyring_migration", lambda: None)

    original_init = SecretManager.__init__

    def mocked_init(self: SecretManager, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.providers = [provider]

    monkeypatch.setattr(SecretManager, "__init__", mocked_init)

    yield provider


@pytest.fixture
def capture_chutils_logs() -> LogCapture:
    """
    Фикстура для перехвата логов.

    - Перехватывает все логи, проходящие через любой логгер (включая те, 
      где `propagate=False`).
    - Позволяет проверять сообщения и поля контекста (например, добавленные через `bind_context`).

    Example:
        def test_logging(capture_chutils_logs):
            from chutils.logger import setup_logger
            logger = setup_logger("test")
            logger.info("Hello world")
            assert capture_chutils_logs.has_message("Hello")
    """
    handler = LogCaptureHandler()

    import logging
    import unittest.mock

    original_call_handlers = logging.Logger.callHandlers

    def mocked_call_handlers(self: logging.Logger, record: logging.LogRecord) -> None:
        # Используем атрибут у рекорда, чтобы не захватывать одну и ту же запись несколько раз
        # при распространении (propagation) вверх по иерархии логгеров.
        if not getattr(record, "_chutils_captured", False):
            handler.emit(record)
            try:
                setattr(record, "_chutils_captured", True)
            except (AttributeError, TypeError):
                # В редких случаях record может быть неизменяемым (хотя в logging это не так)
                pass
        return original_call_handlers(self, record)

    # Патчим метод callHandlers у базового класса Logger.
    # Это гарантирует перехват всех логов, даже если у них propagate=False.
    with unittest.mock.patch.object(logging.Logger, "callHandlers", mocked_call_handlers):
        yield LogCapture(handler)
