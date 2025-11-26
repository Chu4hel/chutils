import logging
import os
import time

import pytest

from chutils.logger import SafeTimedRotatingFileHandler, ChutilsLogger


@pytest.fixture
def time_machine(monkeypatch):
    """
    Фикстура для управления временем.
    Патчит time.time и os.stat, чтобы тесты ротации работали предсказуемо.
    Автоматически доступна во всех тестах внутри tests/logger/
    """

    class TimeMachine:
        def __init__(self, initial_time=1700000000.0):
            self.current_time = initial_time

        def time(self):
            return self.current_time

        def advance(self, seconds):
            self.current_time += seconds

    tm = TimeMachine()

    # 1. Патчим time.time
    monkeypatch.setattr(time, 'time', tm.time)

    # 2. Патчим os.stat (нужно для RotatingFileHandler, чтобы он видел "старое" время изменения файла)
    original_os_stat = os.stat

    class MockStatResult:
        def __init__(self, original_stat_result):
            self._original = original_stat_result

        def __getattr__(self, name):
            if name == 'st_mtime':
                return tm.time()
            return getattr(self._original, name)

    def mock_stat(path, *args, **kwargs):
        # pyfakefs может не создать файл к моменту вызова stat, если мы только настраиваем логгер
        # но для теста это обычно не критично, если файл создается логгером.
        # Если используете pyfakefs, original_os_stat уже пропатчен им, так что это безопасно.
        try:
            res = original_os_stat(path, *args, **kwargs)
            return MockStatResult(res)
        except FileNotFoundError:
            # Если файла нет, пробрасываем ошибку дальше
            raise

    monkeypatch.setattr(os, 'stat', mock_stat)

    return tm


@pytest.fixture
def fast_rotation(monkeypatch):
    """
    Патчит SafeTimedRotatingFileHandler, чтобы ротация 'D' (дни)
    работала как 'S' (секунды). Это ускоряет тесты.
    """
    original_init = SafeTimedRotatingFileHandler.__init__

    def new_init(self, filename, when='D', interval=1, backupCount=0, encoding=None, delay=False, utc=False):
        # Подменяем 'D' на 'S'
        super(SafeTimedRotatingFileHandler, self).__init__(
            filename, when='S', interval=1, backupCount=backupCount,
            encoding=encoding, delay=delay, utc=utc
        )

    monkeypatch.setattr(SafeTimedRotatingFileHandler, '__init__', new_init)


@pytest.fixture
def reset_chutils_state(monkeypatch):
    """
    Сбрасывает глобальное состояние модулей config и logger.
    Позволяет тестам инициализировать пути "с чистого листа".
    """
    from chutils import logger as chutils_logger
    from chutils import config as chutils_config

    monkeypatch.setattr(chutils_logger, '_LOG_DIR', None)
    monkeypatch.setattr(chutils_logger, '_initialization_message_shown', False)
    monkeypatch.setattr(chutils_config, '_BASE_DIR', None)
    monkeypatch.setattr(chutils_config, '_CONFIG_FILE_PATH', None)
    monkeypatch.setattr(chutils_config, '_paths_initialized', False)
    monkeypatch.setattr(chutils_config, '_config_object', None)
    monkeypatch.setattr(chutils_config, '_config_loaded', False)


@pytest.fixture
def force_chutils_logger(mocker):
    """
    Фикстура-фабрика. Возвращает функцию, которая мокает logging.getLogger,
    чтобы для указанных имен он возвращал экземпляр ChutilsLogger.
    """
    original_get_logger = logging.getLogger

    def _apply_mock(target_names):
        # Если передали одну строку, превращаем в список
        if isinstance(target_names, str):
            target_names = [target_names]

        def side_effect(name=None):
            if name in target_names:
                return ChutilsLogger(name)
            return original_get_logger(name)

        return mocker.patch("logging.getLogger", side_effect=side_effect)

    return _apply_mock
