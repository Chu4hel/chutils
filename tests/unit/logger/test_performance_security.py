import logging

from chutils.logger import setup_logger
from chutils.logger.core import _async_listeners


def test_async_logging_integration(reset_chutils_state):
    """Проверяет, что асинхронный логгер действительно создает QueueHandler."""
    logger = setup_logger(
        name="test_async",
        use_async=True,
        force_reconfigure=True
    )

    # Проверяем наличие QueueHandler среди обработчиков
    handlers = logger.handlers
    assert any(isinstance(h, logging.handlers.QueueHandler) for h in handlers)

    # Проверяем, что создано не более одного QueueHandler (при повторной настройке может быть иначе, но здесь свежий)
    queue_handlers = [h for h in handlers if isinstance(h, logging.handlers.QueueHandler)]
    assert len(queue_handlers) == 1

    # Проверяем, что слушатель зарегистрирован в глобальном списке
    assert len(_async_listeners) > 0


def test_custom_masking_regex(reset_chutils_state):
    """Проверяет маскирование через кастомные регулярные выражения."""
    logger = setup_logger(
        name="test_mask_regex",
        custom_patterns=[r"ID-\d{4}"],
        force_reconfigure=True
    )

    # Нам нужен StreamHandler для перехвата вывода, но проще проверить через фильтры
    mask_filter = next(f for f in logger.filters if hasattr(f, 'filter'))

    # Создаем фиктивную запись лога
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py", lineno=1,
        msg="User identifier is ID-1234", args=(), exc_info=None
    )

    mask_filter.filter(record)
    assert record.msg == "User identifier is [MASKED]"


def test_predefined_patterns(reset_chutils_state):
    """Проверяет работу предустановленных паттернов (email)."""
    logger = setup_logger(
        name="test_predefined",
        use_predefined_patterns=["email"],
        force_reconfigure=True
    )

    mask_filter = next(f for f in logger.filters if hasattr(f, 'filter'))

    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py", lineno=1,
        msg="Contact me at secret@example.com please", args=(), exc_info=None
    )

    mask_filter.filter(record)
    assert record.msg == "Contact me at [MASKED] please"


def test_async_no_loss_on_shutdown(reset_chutils_state, tmp_path):
    """Проверяет, что логи не теряются при асинхронном режиме (симулируем запись)."""
    log_file = tmp_path / "async_shutdown.log"
    logger = setup_logger(
        name="test_shutdown",
        log_file_name=str(log_file),
        use_async=True,
        force_reconfigure=True
    )

    logger.info("Message before shutdown")

    # В реальном приложении atexit сработает сам.
    # Здесь мы симулируем остановку слушателей.
    from chutils.logger.core import _stop_all_async_loggers
    _stop_all_async_loggers()

    # Файл должен содержать сообщение (QueueListener.stop() делает flush)
    with open(log_file, "r") as f:
        content = f.read()
        assert "Message before shutdown" in content
