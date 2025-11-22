import logging
import os
import tempfile
import time
from pathlib import Path

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


def test_setup_logger_with_custom_file_name(config_fs, mocker, monkeypatch, caplog):
    """
    Проверяет, что setup_logger создает лог-файл с указанным именем,
    игнорируя настройки из конфигурации, путем мокирования хендлера.
    """
    logging.basicConfig(level=logging.DEBUG)  # Добавляем эту строку
    fs, project_root = config_fs
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)

    # Создаем фейковый config.yml, который будет указывать на другой файл
    config_content = """
Logging:
  log_level: "INFO"
  log_file_name: "config_default.log"
"""
    fs.create_file(project_root / "config.yml", contents=config_content)
    fs.create_file(project_root / "pyproject.toml", contents="")  # Маркер проекта

    # Сбрасываем состояние модуля logger, чтобы он переинициализировался с новыми путями
    from chutils import logger as chutils_logger
    from chutils import config as chutils_config

    test_logger_name = "custom_file_test"

    # Мокаем logging.getLogger, чтобы он возвращал наш мок только для нашего тестового логгера
    original_get_logger = logging.getLogger

    def mock_get_logger(name=None):
        if name == test_logger_name:
            return ChutilsLogger(name)
        return original_get_logger(name)

    mocker.patch("logging.getLogger", side_effect=mock_get_logger)

    monkeypatch.setattr(chutils_logger, '_LOG_DIR', None)
    monkeypatch.setattr(chutils_logger, '_initialization_message_shown', False)
    monkeypatch.setattr(chutils_config, '_BASE_DIR', None)
    monkeypatch.setattr(chutils_config, '_CONFIG_FILE_PATH', None)
    monkeypatch.setattr(chutils_config, '_paths_initialized', False)

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


def test_multiple_loggers_different_files(config_fs, mocker, monkeypatch, caplog):
    """
    Проверяет, что два логгера, созданные с разными `log_file_name`,
    пишут в разные файлы, путем мокирования хендлера.
    """
    logging.basicConfig(level=logging.DEBUG)
    fs, project_root = config_fs
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)
    fs.create_file(project_root / "pyproject.toml", contents="")  # Маркер проекта

    # Мокаем logging.getLogger, чтобы он возвращал свежие экземпляры для наших логгеров
    original_get_logger = logging.getLogger

    def mock_get_logger(name=None):
        if name in ["logger1", "logger2"]:
            return ChutilsLogger(name)
        return original_get_logger(name)

    mocker.patch("logging.getLogger", side_effect=mock_get_logger)

    # Сбрасываем состояние модулей
    from chutils import logger as chutils_logger
    from chutils import config as chutils_config
    monkeypatch.setattr(chutils_logger, '_LOG_DIR', None)
    monkeypatch.setattr(chutils_logger, '_initialization_message_shown', False)
    monkeypatch.setattr(chutils_config, '_BASE_DIR', None)
    monkeypatch.setattr(chutils_config, '_CONFIG_FILE_PATH', None)
    monkeypatch.setattr(chutils_config, '_paths_initialized', False)

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


def test_multiple_loggers_rotation(config_fs, monkeypatch):
    """
    Проверяет, что несколько логгеров с разными файлами ротируются независимо.
    """
    fs, project_root = config_fs
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)
    fs.create_file(project_root / "pyproject.toml", contents="")

    from chutils.logger import SafeTimedRotatingFileHandler

    class TimeMachine:
        def __init__(self, initial_time=1700000000.0): self.current_time = initial_time

        def time(self): return self.current_time

        def advance(self, seconds): self.current_time += seconds

    time_machine = TimeMachine()
    monkeypatch.setattr(time, 'time', time_machine.time)

    original_os_stat = os.stat

    class MockStatResult:
        def __init__(self, original_stat_result): self._original = original_stat_result

        def __getattr__(self, name):
            if name == 'st_mtime': return time_machine.time()
            return getattr(self._original, name)

    def mock_stat(path, *args, **kwargs):
        # В pyfakefs файл может не существовать до первого лога, создадим его, если нужно.
        if not fs.exists(path):
            fs.create_file(path)
        return MockStatResult(original_os_stat(path, *args, **kwargs))

    monkeypatch.setattr(os, 'stat', mock_stat)

    # ----------------------------------------------------

    def new_init(self, filename, when='D', interval=1, backupCount=0, encoding=None, delay=False, utc=False):
        super(SafeTimedRotatingFileHandler, self).__init__(filename, when='S', interval=1, backupCount=backupCount,
                                                           encoding=encoding, delay=delay, utc=utc)

    monkeypatch.setattr(SafeTimedRotatingFileHandler, '__init__', new_init)

    logging.shutdown()

    os.chdir(project_root)

    logger1 = setup_logger("logger1", log_file_name="rotation1.log", force_reconfigure=True)
    logger2 = setup_logger("logger2", log_file_name="rotation2.log", force_reconfigure=True)

    logger1.info("Logger 1 - message 1")
    logger2.info("Logger 2 - message 1")

    time_machine.advance(1.1)
    logger1.info("Logger 1 - message 2")

    time_machine.advance(1.1)
    logger2.info("Logger 2 - message 2")

    logging.shutdown()

    log_files = fs.listdir(logs_dir)
    assert "rotation1.log" in log_files
    assert "rotation2.log" in log_files

    rotated1_found = any(f.startswith("rotation1.log.") for f in log_files)
    rotated2_found = any(f.startswith("rotation2.log.") for f in log_files)

    assert rotated1_found, "Не найден ротированный файл для logger1"
    assert rotated2_found, "Не найден ротированный файл для logger2"


def test_log_rotation_no_permission_error(config_fs, monkeypatch, caplog):
    """
    Тестирует ротацию логов с использованием pyfakefs.
    """
    # --- Подготовка окружения для теста ---
    fs, project_root = config_fs
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)
    fs.create_file(project_root / "config.yml", contents="""
Logging:
  log_level: "DEBUG"
  log_file_name: "test_rotation.log"
  log_backup_count: 5
""")
    fs.create_file(project_root / "pyproject.toml", contents="")

    from chutils.logger import setup_logger, SafeTimedRotatingFileHandler
    from chutils import config as chutils_config

    class TimeMachine:
        def __init__(self, initial_time=1700000000.0): self.current_time = initial_time

        def time(self): return self.current_time

        def advance(self, seconds): self.current_time += seconds

    time_machine = TimeMachine()
    monkeypatch.setattr(time, 'time', time_machine.time)

    original_os_stat = os.stat

    class MockStatResult:
        def __init__(self, original_stat_result): self._original = original_stat_result

        def __getattr__(self, name):
            if name == 'st_mtime': return time_machine.time()
            return getattr(self._original, name)

    def mock_stat(path, *args, **kwargs):
        if not fs.exists(path):
            fs.create_file(path)
        return MockStatResult(original_os_stat(path, *args, **kwargs))

    monkeypatch.setattr(os, 'stat', mock_stat)

    # ----------------------------------------------------

    def new_init(self, filename, when='D', interval=1, backupCount=0, encoding=None, delay=False, utc=False):
        # Принудительно устанавливаем ротацию каждую секунду для теста
        super(SafeTimedRotatingFileHandler, self).__init__(filename, when='S', interval=1, backupCount=backupCount,
                                                           encoding=encoding, delay=delay, utc=utc)

    monkeypatch.setattr(SafeTimedRotatingFileHandler, '__init__', new_init)

    logging.shutdown()
    monkeypatch.setattr(chutils_config, '_paths_initialized', False)

    os.chdir(project_root)

    logger = setup_logger("rotation_test", force_reconfigure=True)

    for i in range(3):
        logger.info(f"Log message {i}")
        time_machine.advance(1.1)

    logging.shutdown()

    log_files = fs.listdir(logs_dir)
    assert "test_rotation.log" in log_files
    assert len(log_files) > 1, f"Ожидалось > 1 лог-файла, но найдено: {log_files}"


def test_rotation_on_real_filesystem_is_working(monkeypatch):
    """
    ФИНАЛЬНЫЙ ТЕСТ НА РЕАЛЬНОЙ ФС:
    Проверяет, что ротация работает, когда мы контролируем ОБА источника времени:
    time.time() и os.stat().
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)
        print(f"\n--- [DEBUG] Тест запущен во временной директории: {logs_dir} ---")

        from chutils.logger import setup_logger, SafeTimedRotatingFileHandler

        # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: ПОЛНЫЙ КОНТРОЛЬ НАД ВРЕМЕНЕМ ---

        class TimeMachine:
            def __init__(self, initial_time=1700000000.0):
                self.current_time = initial_time

            def time(self):
                return self.current_time

            def advance(self, seconds):
                self.current_time += seconds

        time_machine = TimeMachine()
        monkeypatch.setattr(time, 'time', time_machine.time)

        # Патч для os.stat, чтобы он возвращал наше "машинное" время
        original_os_stat = os.stat

        # Создаем обертку над результатом os.stat
        class MockStatResult:
            def __init__(self, original_stat_result):
                self._original = original_stat_result

            def __getattr__(self, name):
                # Для st_mtime возвращаем наше время, для всего остального - реальные значения
                if name == 'st_mtime':
                    return time_machine.time()
                return getattr(self._original, name)

        def mock_stat(path, *args, **kwargs):
            # Вызываем реальный stat, но оборачиваем результат в наш мок
            return MockStatResult(original_os_stat(path, *args, **kwargs))

        monkeypatch.setattr(os, 'stat', mock_stat)

        # -----------------------------------------------------------

        # Патчим __init__ для ежесекундной ротации
        def new_init(self, filename, when='D', interval=1, backupCount=0, encoding=None, delay=False, utc=False):
            super(SafeTimedRotatingFileHandler, self).__init__(filename, when='S', interval=1, backupCount=backupCount,
                                                               encoding=encoding, delay=delay, utc=utc)

        monkeypatch.setattr(SafeTimedRotatingFileHandler, '__init__', new_init)

        # Полностью сбрасываем состояние logging
        logging.shutdown()

        # Настраиваем логгер
        log_file_path = logs_dir / "rotation_debug.log"
        # Создаем пустой файл перед инициализацией логгера, чтобы os.stat сработал
        log_file_path.touch()
        logger = setup_logger("debug_logger", log_file_name=str(log_file_path), force_reconfigure=True)

        # Логируем
        logger.info("Message 1")  # time = 1700000000.0

        time_machine.advance(1.1)
        logger.info("Message 2")  # time = 1700000001.1 -> должна произойти ротация

        time_machine.advance(1.1)
        logger.info("Message 3")  # time = 1700000002.2 -> должна произойти еще одна ротация

        # Освобождаем файлы перед проверкой
        logging.shutdown()

        actual_files = os.listdir(logs_dir)
        print(f"--- [DEBUG] Файлы, найденные в директории: {actual_files} ---")

        assert "rotation_debug.log" in actual_files, "Основной лог-файл не найден!"

        rotated_found = any(f.startswith("rotation_debug.log.") for f in actual_files)
        assert rotated_found, "Ротированные лог-файлы не найдены!"


def test_size_based_rotation(config_fs, monkeypatch):
    """
    Проверяет, что ротация по размеру работает корректно.
    """
    fs, project_root = config_fs
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)
    fs.create_file(project_root / "pyproject.toml", contents="")

    logging.shutdown()
    from chutils import config as chutils_config
    monkeypatch.setattr(chutils_config, '_paths_initialized', False)

    os.chdir(project_root)

    logger = setup_logger(
        "size_rotation_logger",
        log_file_name="size_rotation.log",
        rotation_type='size',
        max_bytes=100,
        backup_count=2,
        force_reconfigure=True
    )

    # Логируем сообщения, чтобы превысить max_bytes
    for i in range(10):
        logger.info(f"This is a log message number {i}")

    logging.shutdown()

    log_files = fs.listdir(logs_dir)
    assert "size_rotation.log" in log_files
    assert "size_rotation.log.1" in log_files


def test_compression_on_rotation(tmp_path, monkeypatch):
    """
    Проверяет, что сжатие ротированных логов работает на реальной ФС.
    """
    project_root = tmp_path
    logs_dir = project_root / "logs"
    logs_dir.mkdir()
    (project_root / "pyproject.toml").touch()

    # Принудительно сбрасываем состояние модулей config и logger
    # чтобы они переинициализировались с новыми путями
    logging.shutdown()
    from chutils import config as chutils_config
    from chutils import logger as chutils_logger
    monkeypatch.setattr(chutils_config, '_BASE_DIR', None)
    monkeypatch.setattr(chutils_config, '_CONFIG_FILE_PATH', None)
    monkeypatch.setattr(chutils_config, '_paths_initialized', False)
    monkeypatch.setattr(chutils_logger, '_LOG_DIR', None)
    monkeypatch.setattr(chutils_logger, '_initialization_message_shown', False)

    # Переходим в временную директорию, чтобы chutils нашел корень проекта
    os.chdir(project_root)

    logger = setup_logger(
        "compression_logger",
        log_file_name="compression.log",
        rotation_type='size',
        max_bytes=100,
        backup_count=2,
        compress=True,
        force_reconfigure=True
    )

    # Логируем сообщения, чтобы вызвать несколько ротаций
    for i in range(10):
        logger.info(f"This is a log message number {i}")

    # Закрываем все хендлеры, чтобы файлы были записаны на диск
    logging.shutdown()

    log_files = os.listdir(logs_dir)

    # Проверяем, что основной лог на месте
    assert "compression.log" in log_files

    # Проверяем, что сжатые бэкапы существуют, а несжатые - удалены
    for i in range(1, 3):  # backup_count=2
        compressed_file = f"compression.log.{i}.gz"
        uncompressed_file = f"compression.log.{i}"
        assert compressed_file in log_files, f"Сжатый файл {compressed_file} не найден"
        assert uncompressed_file not in log_files, f"Несжатый файл {uncompressed_file} не был удален"
