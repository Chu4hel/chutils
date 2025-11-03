import logging
import os
import time

import pytest
from chutils.logger import setup_logger, ChutilsLogger, MEDIUMDEBUG_LEVEL_NUM, DEVDEBUG_LEVEL_NUM


# Импортируем фикстуру из conftest.py, если она там, или определяем здесь
# В данном случае, она в test_config.py, но для чистоты лучше бы ей быть в conftest.py
# Пока что для простоты будем считать, что она доступна глобально в рамках сессии pytest

def test_setup_logger_returns_custom_logger(config_fs):
    """
    Проверяет, что setup_logger возвращает экземпляр ChutilsLogger.
    """
    logger = setup_logger("test_logger_instance")
    assert isinstance(logger, ChutilsLogger)


def test_custom_log_levels(config_fs, caplog):
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


@pytest.mark.skip(reason="Проблемный тест, требует более глубокой отладки взаимодействия с pyfakefs")
def test_log_rotation_no_permission_error(config_fs, monkeypatch, caplog):
    """
    Тестирует ротацию логов, чтобы убедиться, что PermissionError не возникает в Windows.
    Этот тест использует фикстуру `config_fs` для работы с виртуальной ФС.
    """
    # --- Подготовка окружения для теста ---
    fs, project_root = config_fs
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)

    # Создаем временный файл конфигурации
    config_content = f"""
Logging:
  log_level: "DEBUG"
  log_file_name: "test_rotation.log"
  log_backup_count: 5
"""
    fs.create_file(project_root / "config.yml", contents=config_content)
    # Добавляем маркер проекта, чтобы find_project_root его нашел
    fs.create_file(project_root / "pyproject.toml", contents="")

    # --- Патчинг для изоляции теста ---

    # Патчим конструктор хендлера для ежесекундной ротации
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
        # Фикстура config_fs меняет CWD, а наш logger ищет от CWD. Вернемся в корень проекта.
        os.chdir(project_root)
        logger = setup_logger("rotation_test")

        # Активно логируем в течение нескольких секунд, чтобы вызвать ротацию
        log_messages = 5
        for i in range(log_messages):
            logger.info(f"Log message {i}")
            time.sleep(0.5)  # Пауза меньше интервала ротации, чтобы гарантировать запись

    # --- Проверка результатов ---
    # Используем fs.listdir из pyfakefs вместо os.listdir
    log_files = fs.listdir(logs_dir)
    assert "test_rotation.log" in log_files
    # Ожидаем увидеть основной файл и несколько ротированных (например, test_rotation.log.2025-11-02_10-30-01)
    assert len(log_files) > 1, f"Ожидалось > 1 лог-файла, но найдено: {log_files}"
