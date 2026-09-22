"""
Тесты для реестра глобальных хэндлеров, параметра propagate и перехвата стандартного логирования.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from chutils.logger import (
    InterceptHandler,
    add_global_handler,
    capture_standard_logging,
    clear_global_handlers,
    get_global_handlers,
    intercept_all,
    remove_global_handler,
    restore_standard_logging,
    setup_logger,
)


class DummyHandler(logging.Handler):
    """Тестовый хэндлер, сохраняющий записи в список."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture(autouse=True)
def cleanup_logging_state() -> None:
    """Очищает глобальные хэндлеры и интерцепторы до и после каждого теста."""
    clear_global_handlers()
    restore_standard_logging()
    yield
    clear_global_handlers()
    restore_standard_logging()


def test_global_handlers_add_and_remove() -> None:
    """Проверяет добавление и удаление глобальных хэндлеров."""
    h1 = DummyHandler()
    h2 = DummyHandler()

    add_global_handler(h1)
    assert h1 in get_global_handlers()

    # Повторное добавление того же хэндлера не должно дублировать
    add_global_handler(h1)
    assert get_global_handlers().count(h1) == 1

    add_global_handler(h2)
    assert len(get_global_handlers()) == 2

    remove_global_handler(h1)
    assert h1 not in get_global_handlers()
    assert h2 in get_global_handlers()

    clear_global_handlers()
    assert len(get_global_handlers()) == 0


def test_global_handlers_attached_to_existing_and_future_loggers() -> None:
    """Проверяет, что глобальный хэндлер попадает и в уже созданные, и в будущие логгеры."""
    logger_pre = setup_logger("test_global_pre", file_logging=False)

    handler = DummyHandler()
    add_global_handler(handler)

    # Уже созданный логгер должен получить хэндлер
    assert handler in logger_pre.handlers

    # Будущий логгер тоже должен получить хэндлер
    logger_post = setup_logger("test_global_post", file_logging=False)
    assert handler in logger_post.handlers

    logger_pre.info("Message pre")
    logger_post.info("Message post")

    assert len(handler.records) == 2
    assert handler.records[0].getMessage() == "Message pre"
    assert handler.records[1].getMessage() == "Message post"

    remove_global_handler(handler)
    assert handler not in logger_pre.handlers
    assert handler not in logger_post.handlers


def test_setup_logger_propagate_option() -> None:
    """Проверяет работу флага propagate в setup_logger."""
    # По умолчанию propagate = False
    logger_default = setup_logger("test_prop_default", file_logging=False)
    assert logger_default.propagate is False

    # Явный propagate = True
    logger_true = setup_logger(
        "test_prop_true", file_logging=False, propagate=True, force_reconfigure=True
    )
    assert logger_true.propagate is True

    # Явный propagate = False
    logger_false = setup_logger(
        "test_prop_false", file_logging=False, propagate=False, force_reconfigure=True
    )
    assert logger_false.propagate is False


def test_setup_logger_propagate_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет чтение propagate из конфигурации Logging."""
    monkeypatch.setattr(
        "chutils.config.get_config", lambda: {"Logging": {"propagate": True}}
    )

    logger = setup_logger("test_prop_cfg", file_logging=False, force_reconfigure=True)
    assert logger.propagate is True


def test_capture_standard_logging_custom_modules() -> None:
    """Проверяет перехват логов указанных модулей в целевой логгер chutils."""
    target_name = "test_target_logger"
    target_logger = setup_logger(target_name, file_logging=False)

    dest_handler = DummyHandler()
    target_logger.addHandler(dest_handler)

    mod_name = "test_custom_thirdparty"
    capture_standard_logging(
        modules=[mod_name],
        target_logger=target_name,
        level=logging.INFO,
        intercept_root=False,
    )

    third_logger = logging.getLogger(mod_name)
    third_logger.info("Message from third party library")

    assert len(dest_handler.records) == 1
    rec = dest_handler.records[0]
    assert rec.getMessage() == "Message from third party library"
    assert rec.name == mod_name

    restore_standard_logging(modules=[mod_name])


def test_intercept_all_root_interception() -> None:
    """Проверяет перехват через root логгер с intercept_all."""
    target_name = "test_root_target"
    target_logger = setup_logger(target_name, file_logging=False)

    dest_handler = DummyHandler()
    target_logger.addHandler(dest_handler)

    intercept_all(
        modules=[],
        target_logger=target_name,
        level=logging.INFO,
        intercept_root=True,
    )

    # Любой сторонний логгер без явных хэндлеров всплывает в root и перехватывается
    unregistered_logger = logging.getLogger("random_library.core")
    unregistered_logger.info("Root propagated log")

    assert len(dest_handler.records) == 1
    rec = dest_handler.records[0]
    assert rec.getMessage() == "Root propagated log"
    assert rec.name == "random_library.core"

    restore_standard_logging(modules=[], restore_root=True)


def test_intercept_handler_ignores_target_logger_recursion() -> None:
    """Проверяет защиту от рекурсивного перехвата логов самого целевого логгера."""
    handler = InterceptHandler(target_logger_name="my_target")
    record = logging.LogRecord(
        name="my_target",
        level=logging.INFO,
        pathname="path.py",
        lineno=1,
        msg="Self log",
        args=(),
        exc_info=None,
    )

    mock_dest = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(logging, "getLogger", lambda name: mock_dest)
        handler.emit(record)
        mock_dest.handle.assert_not_called()
