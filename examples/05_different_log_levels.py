"""
Пример 5: Различные уровни логирования для разных модулей.

Демонстрирует сценарий, когда в одном приложении нужно видеть подробную отладку
от одного модуля ('core') и только критические ошибки от другого ('utils').
Каждый модуль при этом может писать в свой собственный файл.
"""

from chutils.logger import setup_logger, ChutilsLogger, LogLevel


def main() -> None:
    """
    Создает логгеры с индивидуальными настройками уровней и файлов.
    """
    # 1. Модуль 'Core' - здесь нам важна каждая деталь (уровень DEVDEBUG)
    core_logger: ChutilsLogger = setup_logger(
        "core",
        log_level=LogLevel.DEVDEBUG,
        log_file_name="core_debug.log"
    )

    # 2. Модуль 'Utils' - вспомогательный код, смотрим только ошибки (уровень WARNING)
    utils_logger: ChutilsLogger = setup_logger(
        "utils",
        log_level=LogLevel.WARNING,
        log_file_name="utils_errors.log"
    )

    # 3. Основной логгер (настройки по умолчанию из config.yml)
    app_logger: ChutilsLogger = setup_logger("app")

    print("--- Демонстрация разделения уровней ---")

    app_logger.info("Приложение запущено.")

    # Это сообщение МЫ УВИДИМ, т.к. уровень DEVDEBUG позволяет всё
    core_logger.devdebug("Ядро системы: проверка внутренних ресурсов...")

    # Это сообщение МЫ НЕ УВИДИМ в консоли/файле, т.к. уровень логгера WARNING
    utils_logger.info("Утилита: выполнение фоновой задачи (сообщение INFO)")

    # Это сообщение МЫ УВИДИМ
    utils_logger.error("Утилита: обнаружен сбой при доступе к ресурсу!")

    app_logger.info("Приложение завершило работу. Проверьте файлы в папке logs/.")


if __name__ == "__main__":
    main()
