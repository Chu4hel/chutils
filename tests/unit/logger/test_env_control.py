import logging
import os

from chutils.logger import core as chutils_logger_core


def test_log_no_time_env_var(monkeypatch, capsys):
    """Проверка удаления даты/времени из лога при CH_LOG_NO_TIME=1."""
    monkeypatch.setenv("CH_LOG_NO_TIME", "true")
    # Отключаем Rich для предсказуемого текстового вывода
    monkeypatch.setenv("CH_NO_RICH", "1")

    # Принудительно перенастраиваем логгер
    test_logger = chutils_logger_core.setup_logger("test_no_time", force_reconfigure=True)
    test_logger.info("Test message without time")

    captured = capsys.readouterr()
    # Стандартный формат: 2026-03-17 22:35:59,266 - name - LEVEL - message
    # Ожидаем отсутствие даты в начале строки
    assert "Test message without time" in captured.err
    # Простейшая проверка: строка не должна начинаться с цифр года (20xx)
    import re
    # Регулярка для даты ГГГГ-ММ-ДД
    date_pattern = r"\d{4}-\d{2}-\d{2}"
    assert not re.search(date_pattern, captured.err)


def test_log_no_file_env_var(monkeypatch, tmp_path):
    """Проверка отсутствия файла лога при CH_LOG_NO_FILE=1."""
    monkeypatch.setenv("CH_LOG_NO_FILE", "1")
    log_file = tmp_path / "should_not_exist.log"

    # Сбрасываем кэш обработчиков
    chutils_logger_core._file_handler_cache.clear()

    test_logger = chutils_logger_core.setup_logger(
        "test_no_file",
        log_file_name=str(log_file),
        force_reconfigure=True
    )
    test_logger.info("This should not be in a file")

    # Проверяем, что файл не создался
    assert not os.path.exists(log_file)
    # Проверяем, что у логгера нет FileHandler
    assert not any(isinstance(h, logging.FileHandler) for h in test_logger.handlers)


def test_env_vars_priority_over_params(monkeypatch, capsys, tmp_path):
    """Проверка того, что переменные окружения имеют приоритет над параметрами setup_logger."""
    monkeypatch.setenv("CH_LOG_NO_TIME", "yes")
    monkeypatch.setenv("CH_LOG_NO_FILE", "true")
    # Отключаем Rich для предсказуемого текстового вывода
    monkeypatch.setenv("CH_NO_RICH", "1")

    log_file = tmp_path / "priority_test.log"
    chutils_logger_core._file_handler_cache.clear()

    # Передаем параметры, которые должны быть проигнорированы
    test_logger = chutils_logger_core.setup_logger(
        "test_priority",
        log_file_name=str(log_file),
        force_reconfigure=True
    )
    test_logger.info("Priority test message")

    captured = capsys.readouterr()

    # 1. Нет времени
    import re
    date_pattern = r"\d{4}-\d{2}-\d{2}"
    assert not re.search(date_pattern, captured.err)

    # 2. Нет файла
    assert not os.path.exists(log_file)
