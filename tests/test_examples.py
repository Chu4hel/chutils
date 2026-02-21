import logging

import pytest

import chutils
from chutils.decorators import log_function_details
# Импортируем нужные функции и классы из библиотеки
from chutils.logger import setup_logger, DEVDEBUG_LEVEL_NUM


@pytest.fixture(autouse=True)
def clean_logging_state(caplog, tmp_path):
    """
    Эта фикстура гарантирует, что состояние логирования и конфигурации
    сбрасывается перед каждым тестом.
    """
    # Сохраняем оригинальные пути конфига, если они были установлены
    try:
        original_base_dir = chutils.config._BASE_DIR
        original_config_path = chutils.config._CONFIG_FILE_PATH
        original_config_object = chutils.config._config_object
        original_config_loaded = chutils.config._config_loaded
    except AttributeError:
        original_base_dir = None
        original_config_path = None
        original_config_object = None
        original_config_loaded = False

    # Кэшируем глобальные состояния для логгера и декоратора
    original_log_dir = chutils.logger._LOG_DIR
    original_module_logger = chutils.decorators._module_logger

    # Сбрасываем кэши в модулях chutils
    # Создаем директорию для логов, которую ожидает chutils.logger
    log_dir_for_test = tmp_path / "logs"
    log_dir_for_test.mkdir(exist_ok=True)

    chutils.config._config_object = None
    chutils.config._config_loaded = False
    chutils.logger._file_handler_cache.clear()
    chutils.logger._initialization_message_shown = False

    # ВАЖНО: Очищаем путь директории и инстанс логгера, чтобы не было "утечек" между тестами
    chutils.logger._LOG_DIR = None
    chutils.decorators._module_logger = None

    # Очищаем все логгеры, которые были созданы в предыдущих тестах
    # Это предотвращает "протекание" обработчиков между тестами
    for logger_name in logging.root.manager.loggerDict:
        if logger_name.startswith('chutils') or logger_name in ['main', 'audit', 'events']:
            logger_instance = logging.getLogger(logger_name)
            logger_instance.handlers.clear()
            logger_instance.propagate = True

    yield  # Выполнение теста

    # Восстанавливаем оригинальное состояние после теста
    chutils.config._BASE_DIR = original_base_dir
    chutils.config._CONFIG_FILE_PATH = original_config_path
    chutils.config._config_object = original_config_object
    chutils.config._config_loaded = original_config_loaded
    chutils.logger._LOG_DIR = original_log_dir
    chutils.decorators._module_logger = original_module_logger


def test_decorator_example_logs_correctly(caplog, tmp_path):
    """
    Тест проверяет, что декоратор log_function_details корректно логирует
    информацию о вызове функции.
    """
    # Устанавливаем уровень захвата на DEVDEBUG
    caplog.set_level(DEVDEBUG_LEVEL_NUM)

    # Изолируем создание лог файлов в тестовой директории
    chutils.config._BASE_DIR = str(tmp_path)

    # Настраиваем логгер для модуля декораторов напрямую
    dec_logger = setup_logger(name="chutils.decorators", log_level="DEVDEBUG")

    # ВАЖНО: включаем propagate, так как setup_logger ставит его в False.
    # Без этого caplog не перехватит сообщения, они уйдут только в консоль!
    dec_logger.propagate = True

    # Сохраняем в кэш модуля, чтобы декоратор использовал именно его
    chutils.decorators._module_logger = dec_logger

    @log_function_details
    def decorated_sum(a: int, b: int):
        return a + b

    # Вызываем функцию
    decorated_sum(5, 10)

    # Ищем нужные записи в логах
    decorator_logs = [r for r in caplog.records if r.name == "chutils.decorators"]

    assert len(decorator_logs) >= 2, "Не найдены сообщения от декоратора"

    first_log, second_log = decorator_logs[0], decorator_logs[1]

    # Проверяем уровень и содержание первого сообщения (о вызове)
    assert first_log.levelno == DEVDEBUG_LEVEL_NUM
    assert "Вызов функции: decorated_sum()" in first_log.message

    # Проверяем уровень и содержание второго сообщения (о результате)
    assert second_log.levelno == DEVDEBUG_LEVEL_NUM
    assert "Функция decorated_sum() завершилась за" in second_log.message
    assert "Возвращаемое значение: 15" in second_log.message


def test_multiple_loggers_example_logs_correctly(caplog, tmp_path):
    """
    Тест проверяет, что можно настроить и использовать несколько логгеров
    с разными конфигурациями из файла.
    """
    # Устанавливаем уровень захвата логов для этого теста
    caplog.set_level(logging.DEBUG)

    # --- Подготовка тестового окружения ---
    # Создаем временный config.yml, который будет использоваться в тесте
    example_config_content = """
Logging:
  log_level: INFO
  log_file_name: "main.log"
AuditLogger:
  log_level: DEBUG
  log_file_name: "audit.log"
EventLogger:
  log_level: INFO
  log_file_name: "events.log"
"""
    # Указываем chutils на нашу временную директорию как на корень проекта
    chutils.config._BASE_DIR = str(tmp_path)
    tmp_config_file = tmp_path / "config.yml"
    tmp_config_file.write_text(example_config_content, encoding='utf-8')
    chutils.config._CONFIG_FILE_PATH = str(tmp_config_file)

    (tmp_path / "logs").mkdir(exist_ok=True)

    # --- Выполнение логики, аналогичной примеру ---
    main_logger = setup_logger("main")
    audit_logger = setup_logger("audit", config_section_name="AuditLogger")
    event_logger = setup_logger("events", config_section_name="EventLogger")

    # ВАЖНО: Разрешаем propagate для перехвата в pytest caplog
    main_logger.propagate = True
    audit_logger.propagate = True
    event_logger.propagate = True

    main_logger.info("Сообщение от основного логгера.")
    audit_logger.debug("Детальное сообщение для аудита.")
    event_logger.info("Логгер событий использует ротацию по времени.")

    # --- Проверка результатов ---
    # Создаем множество из сообщений для удобного поиска
    log_tuples = {(r.name, r.levelname, r.message) for r in caplog.records}

    # Проверяем, что все ожидаемые сообщения присутствуют
    assert ("main", "INFO", "Сообщение от основного логгера.") in log_tuples
    assert ("audit", "DEBUG", "Детальное сообщение для аудита.") in log_tuples
    assert ("events", "INFO", "Логгер событий использует ротацию по времени.") in log_tuples
