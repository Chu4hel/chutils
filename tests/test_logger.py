import logging
import os
import time

from chutils.logger import setup_logger, ChutilsLogger, MEDIUMDEBUG_LEVEL_NUM, DEVDEBUG_LEVEL_NUM


def test_setup_logger_returns_custom_logger():
    """
    Проверяет, что setup_logger возвращает экземпляр ChutilsLogger.
    """
    logger = setup_logger("test_logger_instance")
    assert isinstance(logger, ChutilsLogger)


def test_custom_log_levels(caplog):
    """
    Проверяет, что кастомные уровни логирования работают корректно.
    """
    logger = setup_logger("test_custom_levels")

    # Сценарий 1: Уровень DEBUG (10)
    # devdebug (9) не должен проходить, остальные - должны
    logger.setLevel(logging.DEBUG)
    with caplog.at_level(DEVDEBUG_LEVEL_NUM):
        logger.devdebug("dev_msg")
        logger.debug("debug_msg")
        logger.mediumdebug("medium_msg")

    assert "dev_msg" not in caplog.text
    assert "debug_msg" in caplog.text
    assert "medium_msg" in caplog.text

    caplog.clear()

    # Сценарий 2: Уровень MEDIUMDEBUG (15)
    # devdebug (9) и debug (10) не должны проходить
    logger.setLevel(MEDIUMDEBUG_LEVEL_NUM)
    with caplog.at_level(DEVDEBUG_LEVEL_NUM):
        logger.devdebug("dev_msg")
        logger.debug("debug_msg")
        logger.mediumdebug("medium_msg")
        logger.info("info_msg")

    assert "dev_msg" not in caplog.text
    assert "debug_msg" not in caplog.text
    assert "medium_msg" in caplog.text
    assert "info_msg" in caplog.text

    caplog.clear()

    # Сценарий 3: Уровень DEVDEBUG (9)
    # Все сообщения должны проходить
    logger.setLevel(DEVDEBUG_LEVEL_NUM)
    with caplog.at_level(DEVDEBUG_LEVEL_NUM):
        logger.devdebug("dev_msg")
        logger.debug("debug_msg")

    assert "dev_msg" in caplog.text
    assert "debug_msg" in caplog.text


def test_log_rotation_no_permission_error(tmp_path, monkeypatch, caplog):
    """
    Тестирует ротацию логов, чтобы убедиться, что PermissionError не возникает в Windows.
    Тест настраивает логгер с ротацией каждую секунду, активно пишет в лог
    и проверяет, что создаются ротированные файлы без ошибок.
    """
    # --- Подготовка окружения для теста ---

    # Создаем временную структуру директорий
    project_root = tmp_path
    logs_dir = project_root / "logs"
    logs_dir.mkdir()

    # Создаем временный файл конфигурации
    config_content = f"""
Logging:
  log_level: "DEBUG"
  log_file_name: "test_rotation.log"
  log_backup_count: 5
"""
    # В chutils поиск конфига идет из chutils.config._initialize_paths()
    # Он ищет pyproject.toml или .git. Создадим один из них.
    (project_root / "pyproject.toml").write_text("")
    config_file = project_root / "config.yml"
    config_file.write_text(config_content, encoding='utf-8')

    # --- Патчинг для изоляции теста ---

    # Меняем CWD на временную директорию, чтобы chutils корректно нашел корень проекта
    monkeypatch.chdir(project_root)

    # Патчим модуль config, сбрасывая его состояние, чтобы он переинициализировался
    from chutils import config as chutils_config
    monkeypatch.setattr(chutils_config, '_paths_initialized', False)
    monkeypatch.setattr(chutils_config, '_config_object', None)
    monkeypatch.setattr(chutils_config, '_config_loaded', False)

    # Патчим конструктор хендлера, чтобы ротация была каждую секунду
    from chutils.logger import SafeTimedRotatingFileHandler
    original_init = SafeTimedRotatingFileHandler.__init__

    def new_init(self, filename, when='D', interval=1, backupCount=0, encoding=None, delay=False, utc=False):
        # Принудительно устанавливаем ротацию каждую секунду для теста
        super(SafeTimedRotatingFileHandler, self).__init__(filename, when='S', interval=1, backupCount=backupCount,
                                                           encoding=encoding, delay=delay, utc=utc)

    monkeypatch.setattr(SafeTimedRotatingFileHandler, '__init__', new_init)

    # Сбрасываем состояние модуля logger, чтобы он переинициализировался с новыми путями
    from chutils import logger as chutils_logger
    # Удаляем существующие обработчики у всех логгеров, чтобы избежать дублирования
    for logger_name in logging.Logger.manager.loggerDict:
        logging.getLogger(logger_name).handlers = []
    monkeypatch.setattr(chutils_logger, '_LOG_DIR', None)
    monkeypatch.setattr(chutils_logger, '_logger_instance', None)
    monkeypatch.setattr(chutils_logger, '_initialization_message_shown', False)

    # --- Выполнение теста ---

    # Настраиваем и получаем логгер. Теперь он будет использовать наши временные настройки.
    # Используем caplog, чтобы видеть вывод логгера в тесте
    with caplog.at_level(logging.DEBUG):
        logger = setup_logger("rotation_test")

        # Активно логируем в течение нескольких секунд, чтобы вызвать ротацию
        log_messages = 5
        for i in range(log_messages):
            logger.info(f"Log message {i}")
            time.sleep(0.5)  # Пауза меньше интервала ротации, чтобы гарантировать запись

    # --- Проверка результатов ---

    # Проверяем, что основной лог-файл и ротированные бэкапы были созданы
    log_files = os.listdir(logs_dir)
    assert "test_rotation.log" in log_files
    # Ожидаем увидеть основной файл и несколько ротированных (например, test_rotation.log.2025-11-02_10-30-01)
    assert len(log_files) > 1, f"Ожидалось > 1 лог-файла, но найдено: {log_files}"

    # Самая главная проверка неявная: если бы возник PermissionError, тест бы упал.
    # Если мы дошли до этой точки, значит, ротация прошла без ошибок доступа.
    print(f"Тест успешно завершен. Найденные лог-файлы: {log_files}")
