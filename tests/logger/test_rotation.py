import logging
import os
import tempfile
from pathlib import Path

from chutils.logger import setup_logger


def test_multiple_loggers_rotation(project_with_marker, time_machine, fast_rotation):
    """Проверяет независимую ротацию нескольких логгеров."""
    fs, project_root = project_with_marker
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)

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
    assert any(f.startswith("rotation1.log.") for f in log_files)
    assert any(f.startswith("rotation2.log.") for f in log_files)


def test_log_rotation_no_permission_error(project_with_marker, time_machine, fast_rotation, monkeypatch):
    """Тестирует базовую ротацию с pyfakefs."""
    fs, project_root = project_with_marker
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)
    fs.create_file(project_root / "config.yml",
                   contents='Logging:\n  log_level: "DEBUG"\n  log_file_name: "test_rotation.log"\n  log_backup_count: 5\n')

    from chutils import config as chutils_config
    logging.shutdown()
    monkeypatch.setattr(chutils_config, '_paths_initialized', False)
    os.chdir(project_root)

    logger = setup_logger("rotation_test", force_reconfigure=True)

    for i in range(3):
        logger.info(f"Log message {i}")
        time_machine.advance(1.1)

    logging.shutdown()
    assert len(fs.listdir(logs_dir)) > 1


def test_rotation_on_real_filesystem_is_working(time_machine, fast_rotation):
    """Финальный тест ротации на реальной ФС во временной папке."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)
        logging.shutdown()

        # Создаем пустой файл, чтобы os.stat сработал корректно
        log_file_path = logs_dir / "rotation_debug.log"
        log_file_path.touch()

        logger = setup_logger("debug_logger", log_file_name=str(log_file_path), force_reconfigure=True)

        logger.info("Message 1")
        time_machine.advance(1.1)
        logger.info("Message 2")
        time_machine.advance(1.1)
        logger.info("Message 3")

        logging.shutdown()

        actual_files = os.listdir(logs_dir)
        assert "rotation_debug.log" in actual_files
        assert any(f.startswith("rotation_debug.log.") for f in actual_files)


def test_size_based_rotation(project_with_marker, monkeypatch):
    """Проверяет ротацию по размеру."""
    fs, project_root = project_with_marker
    logs_dir = project_root / "logs"
    fs.create_dir(logs_dir)

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

    for i in range(10):
        logger.info(f"This is a log message number {i}")

    logging.shutdown()

    log_files = fs.listdir(logs_dir)
    assert "size_rotation.log" in log_files
    assert "size_rotation.log.1" in log_files
