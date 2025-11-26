import logging
import os

from chutils.logger import setup_logger


def test_compression_on_rotation(tmp_path, reset_chutils_state):
    """Проверяет сжатие логов."""
    project_root = tmp_path
    logs_dir = project_root / "logs"
    logs_dir.mkdir()
    (project_root / "pyproject.toml").touch()

    # Сбрасываем хендлеры, чтобы освободить файлы (на Windows критично)
    logging.shutdown()

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

    for i in range(10):
        logger.info(f"This is a log message number {i}")

    logging.shutdown()
    log_files = os.listdir(logs_dir)

    assert "compression.log" in log_files
    # Проверяем наличие .gz и отсутствие сырых .1
    for i in range(1, 3):
        assert f"compression.log.{i}.gz" in log_files
        assert f"compression.log.{i}" not in log_files
