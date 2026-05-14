"""
Пример использования Hot-Reload конфигурации.

Этот скрипт демонстрирует, как приложение может автоматически реагировать на изменения
в файле конфигурации без перезагрузки.
"""

import time
from pathlib import Path

from chutils import (
    get_config_value,
    save_config_value,
    start_config_watcher,
    stop_config_watcher,
    on_config_change,
    setup_logger
)

# Настраиваем логгер для наглядности
logger = setup_logger()


def my_callback():
    """Эта функция будет вызвана при изменении файла."""
    logger.info("--- Сигнал от watcher: Конфигурация изменилась! ---")
    new_val = get_config_value("App", "greeting", "Default Hello")
    logger.info(f"Обновленное приветствие: {new_val}")


def main():
    # Создаем временный файл конфигурации для теста
    config_path = Path("config.yml")
    config_content = """
App:
  greeting: "Hello, World!"
"""
    config_path.write_text(config_content, encoding='utf-8')
    logger.info("Создан временный файл config.yml")

    try:
        # 1. Регистрируем коллбэк
        on_config_change(my_callback)

        # 2. Запускаем мониторинг
        # Если watchdog не установлен, здесь будет брошен ImportError
        try:
            start_config_watcher()
        except ImportError as e:
            logger.error(f"Ошибка: {e}")
            logger.info("Для работы этого примера установите watchdog: pip install chutils[watch]")
            return

        logger.info("Watcher запущен. Текущее приветствие: " + get_config_value("App", "greeting"))
        logger.info("Попробуйте вручную изменить 'greeting' в файле config.yml...")
        logger.info("Или подождите 2 секунды, скрипт начнет автоматические тесты.")

        time.sleep(2)

        # 1. Имитируем программное изменение БЕЗ уведомления (notify=False)
        logger.info("Программное обновление (quiet mode, notify=False)...")
        save_config_value("App", "greeting", "Silent Update", notify=False)
        # Коллбэк my_callback НЕ должен быть вызван (проверьте логи)
        time.sleep(2)

        # 2. Имитируем программное изменение С уведомлением (по умолчанию notify=True)
        logger.info("Программное обновление (с уведомлением)...")
        save_config_value("App", "greeting", "Hello from save_config_value!")
        # Коллбэк my_callback ДОЛЖЕН быть вызван
        time.sleep(2)

        # 3. Имитируем ручное изменение файла другим процессом
        logger.info("Имитация внешнего изменения файла...")
        updated_content = """
App:
  greeting: "Hello from External Process!"
"""
        config_path.write_text(updated_content, encoding='utf-8')

        # Даем немного времени на обработку события (debounce 1.0 сек)
        time.sleep(2)

        logger.info("Завершение примера через 5 секунд...")
        time.sleep(5)

    finally:
        # Всегда останавливайте watcher перед завершением
        stop_config_watcher()

        # Удаляем временный файл
        if config_path.exists():
            config_path.unlink()
            logger.info("Временный файл удален.")


if __name__ == "__main__":
    main()
