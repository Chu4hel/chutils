"""Тесты проверки отсутствия побочных эффектов при авторегистрации pytest-плагина."""

import importlib
from pathlib import Path
import sys

from chutils.logger import setup_logger


def test_fixtures_module_imports_are_lazy() -> None:
    """Проверяет, что импорт плагина chutils.scraping.testing.fixtures не загружает тяжелые модули."""
    modules_to_unload = [
        "chutils.scraping.testing.fixtures",
        "chutils.scraping.testing.server",
        "chutils.scraping.testing.session",
        "chutils.scraping.testing.snapshot",
    ]
    for mod in modules_to_unload:
        sys.modules.pop(mod, None)

    # Импортируем fixtures, как это делает pytest при дискавери плагина [pytest11]
    importlib.import_module("chutils.scraping.testing.fixtures")

    # Проверяем, что server и session не были импортированы на верхнем уровне
    assert "chutils.scraping.testing.server" not in sys.modules
    assert "chutils.scraping.testing.session" not in sys.modules
    assert "chutils.scraping.testing.snapshot" not in sys.modules


def test_setup_logger_delay_does_not_create_file_before_emit(tmp_path: Path) -> None:
    """Проверяет, что setup_logger с delay=True по умолчанию не создает файл лога до первой записи."""
    log_file = tmp_path / "subdir" / "test_delay.log"
    assert not log_file.exists()
    assert not log_file.parent.exists()

    logger = setup_logger("test_delay_logger", log_file_name=str(log_file), force_reconfigure=True)
    # Файл и папка НЕ должны быть созданы до первой реальной записи
    assert not log_file.exists()

    # Записываем сообщение в лог
    logger.info("Проверка ленивой записи")

    # Теперь файл и каталог должны существовать
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Проверка ленивой записи" in content


def test_test_modules_disable_file_logging_by_default() -> None:
    """Проверяет, что для тестовых модулей chutils.*.testing файловый обработчик выключен по умолчанию."""
    import logging

    logger = setup_logger("chutils.scraping.testing.server", force_reconfigure=True)
    assert not any(isinstance(h, logging.FileHandler) for h in logger.handlers)


def test_pytest_runner_disables_default_file_logging() -> None:
    """Проверяет, что под тестовым раннером дефолтный app.log не создается, если не запрошен явно."""
    import logging

    # Обычный логгер без явного файла под pytest не должен иметь FileHandler
    logger = setup_logger("regular_app_logger", force_reconfigure=True)
    assert not any(isinstance(h, logging.FileHandler) for h in logger.handlers)


def test_pytest_runner_allows_file_logging_when_explicitly_requested(tmp_path: Path) -> None:
    """Проверяет, что при явном указании log_file_name или file_logging=True файловый логгер создается."""
    import logging

    # Явный log_file_name
    custom_log = tmp_path / "custom.log"
    logger1 = setup_logger("explicit_file_logger", log_file_name=str(custom_log), force_reconfigure=True)
    assert any(isinstance(h, logging.FileHandler) for h in logger1.handlers)

    # Явный file_logging=True
    logger2 = setup_logger("explicit_flag_logger", file_logging=True, force_reconfigure=True)
    assert any(isinstance(h, logging.FileHandler) for h in logger2.handlers)

