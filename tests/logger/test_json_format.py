import json

import pytest

from chutils.logger import setup_logger


def test_json_format_parameter(capsys, monkeypatch):
    """Проверяет, что параметр json_format=True включает JSON вывод."""
    # Гарантируем, что пакет установлен для этого теста
    # (В реальных тестах он должен быть установлен в окружении)

    logger = setup_logger(name="json_test", json_format=True, force_reconfigure=True)
    logger.info("Test JSON message")

    captured = capsys.readouterr()
    # Проверяем, что вывод - это валидный JSON
    try:
        log_json = json.loads(captured.err.strip().split('\n')[-1])
        assert log_json["message"] == "Test JSON message"
        assert "levelname" in log_json
        assert "name" in log_json
        assert "asctime" in log_json
    except json.JSONDecodeError:
        pytest.fail("Вывод не является валидным JSON")


def test_json_format_env_priority(capsys, monkeypatch):
    """Проверяет приоритет ENV переменной над другими настройками."""
    monkeypatch.setenv("CH_LOG_JSON", "true")

    # Даже если в коде False, ENV должен победить
    logger = setup_logger(name="json_env_test", json_format=False, force_reconfigure=True)
    logger.info("Env wins")

    captured = capsys.readouterr()
    try:
        json.loads(captured.err.strip().split('\n')[-1])
    except json.JSONDecodeError:
        pytest.fail("ENV переменная CH_LOG_JSON=true не включила JSON формат")


def test_json_format_graceful_degradation(capsys, monkeypatch):
    """Проверяет откат к обычному тексту, если пакет не установлен."""
    # Эмулируем отсутствие пакета через флаг
    from chutils import logger as logger_module
    monkeypatch.setattr(logger_module, "JSON_LOGGER_AVAILABLE", False)

    logger_name = "json_missing_test"
    # setup_logger выведет предупреждение в stderr через свой StreamHandler
    logger = setup_logger(name=logger_name, json_format=True, force_reconfigure=True)

    captured = capsys.readouterr()
    assert "пакет 'python-json-logger' не установлен" in captured.err

    logger.info("Standard text message")
    captured = capsys.readouterr()

    # Проверяем, что вывод НЕ является JSON
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.err.strip().split('\n')[-1])
    assert "Standard text message" in captured.err


def test_json_format_masking_integration(capsys, monkeypatch):
    """Проверяет, что маскирование секретов работает в JSON формате."""

    # Регистрируем секрет для маскирования через логгер
    logger = setup_logger(name="json_mask_test", json_format=True, force_reconfigure=True)
    logger.add_mask("supersecret123")

    logger.info("The password is supersecret123")

    captured = capsys.readouterr()
    # Ищем JSON в выводе (может быть несколько строк, берем последнюю)
    lines = captured.err.strip().split('\n')
    log_json = None
    for line in reversed(lines):
        try:
            log_json = json.loads(line)
            break
        except json.JSONDecodeError:
            continue

    if log_json is None:
        pytest.fail("JSON лог не найден в выводе")

    assert "supersecret123" not in log_json["message"]
    assert "***" in log_json["message"]
