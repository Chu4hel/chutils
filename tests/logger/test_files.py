import logging
import os

from chutils import setup_logger


def test_setup_logger_with_custom_file_name(project_with_marker, mocker, caplog, reset_chutils_state,
                                            force_chutils_logger):
    """
    Проверяет, что setup_logger создает лог-файл с указанным именем,
    игнорируя настройки из конфигурации, путем мокирования хендлера.
    """
    logging.basicConfig(level=logging.DEBUG)  # Добавляем эту строку
    fs, project_root = project_with_marker
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)

    # Создаем фейковый config.yml, который будет указывать на другой файл
    config_content = """
Logging:
  log_level: "INFO"
  log_file_name: "config_default.log"
"""
    fs.create_file(project_root / "config.yml", contents=config_content)

    # Используем фикстуру для мока getLogger
    force_chutils_logger("custom_file_test")

    # Устанавливаем уровень логирования для chutils.config на DEBUG
    logging.getLogger('chutils.config').setLevel(logging.DEBUG)

    # Мокаем SafeTimedRotatingFileHandler
    mock_file_handler = mocker.patch("chutils.logger.SafeTimedRotatingFileHandler")
    mock_file_handler.return_value.level = logging.NOTSET  # Устанавливаем уровень для мока

    # Указываем кастомное имя файла
    custom_log_file = "my_custom_logger.log"
    os.chdir(project_root)  # Переходим в корень проекта для корректного поиска

    with caplog.at_level(logging.DEBUG):
        logger = setup_logger("custom_file_test", log_file_name=custom_log_file)
        logger.info("Это сообщение в кастомном файле.")

    # Проверяем, что SafeTimedRotatingFileHandler был вызван с правильным путем
    expected_log_path_str = str(logs_dir / custom_log_file)
    mock_file_handler.assert_called_once()
    actual_log_path_str = mock_file_handler.call_args[0][0]

    normalized_actual = os.path.normpath(actual_log_path_str)
    normalized_expected = os.path.normpath(expected_log_path_str)

    assert normalized_actual.endswith(normalized_expected)

    # Проверяем, что логгер все еще работает (хотя бы в консоль)
    # (Файловый вывод теперь мокнут, поэтому проверяем только логику вызова хендлера)
    logger.info("Еще одно сообщение.")
    assert mock_file_handler.call_count == 1  # Хендлер создается один раз

    # Проверяем логи chutils.config
    assert "Найден маркер 'config.yml' в директории" in caplog.text
    assert "Корень проекта автоматически определен" in caplog.text


def test_multiple_loggers_different_files(project_with_marker, mocker, caplog, reset_chutils_state,
                                          force_chutils_logger):
    """
    Проверяет, что два логгера, созданные с разными `log_file_name`,
    пишут в разные файлы, путем мокирования хендлера.
    """
    logging.basicConfig(level=logging.DEBUG)
    fs, project_root = project_with_marker
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)

    # Используем фикстуру для мока getLogger (для двух имен сразу)
    force_chutils_logger(["logger1", "logger2"])

    os.chdir(project_root)

    # Мокаем SafeTimedRotatingFileHandler
    mock_file_handler = mocker.patch("chutils.logger.SafeTimedRotatingFileHandler")

    # Настраиваем два логгера с разными файлами
    with caplog.at_level(logging.DEBUG):
        logger1 = setup_logger("logger1", log_file_name="logger1.log")
        logger2 = setup_logger("logger2", log_file_name="logger2.log")

    # Проверяем, что хендлер был вызван дважды
    assert mock_file_handler.call_count == 2

    # Проверяем пути, с которыми был вызван хендлер
    call_args = [call[0][0] for call in mock_file_handler.call_args_list]
    expected_path1 = os.path.normpath(str(logs_dir / "logger1.log"))
    expected_path2 = os.path.normpath(str(logs_dir / "logger2.log"))

    # Нормализуем пути перед сравнением
    normalized_call_args = [os.path.normpath(str(arg)) for arg in call_args]

    assert normalized_call_args[0].endswith(expected_path1) or normalized_call_args[0].endswith(expected_path2)
    assert normalized_call_args[1].endswith(expected_path1) or normalized_call_args[1].endswith(expected_path2)
    assert normalized_call_args[0] != normalized_call_args[1]  # Убедимся, что пути разные
