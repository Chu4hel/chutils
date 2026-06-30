"""
Пример 24: Планировщик периодических фоновых задач.

Демонстрирует создание и регистрацию периодических задач (синхронных и асинхронных),
управление перекрытиями (overlap), стратегии ошибок и интеграцию с Graceful Shutdown.
"""

import asyncio
import time

from chutils import periodic_task, start_scheduler, setup_logger, setup_graceful_shutdown
from chutils.tasks import ErrorStrategy

# Настраиваем логгер
logger = setup_logger("task_scheduler_example")


@periodic_task(interval_seconds=2, run_immediately=True, name="async_metric_sender")
async def send_metrics() -> None:
    """Асинхронная периодическая задача."""
    logger.info("Отправка метрик... (async task)")
    await asyncio.sleep(0.1)


@periodic_task(
    interval_seconds=3,
    run_immediately=False,
    overlap=False,
    error_strategy=ErrorStrategy.IGNORE,
    name="sync_cache_cleaner"
)
def clean_cache() -> None:
    """Синхронная периодическая задача."""
    logger.info("Очистка кэша... (sync task)")
    time.sleep(0.2)


async def main() -> None:
    logger.info("Инициализация примера планировщика задач...")

    # Настраиваем Graceful Shutdown для перехвата сигналов (SIGINT, SIGTERM)
    setup_graceful_shutdown()

    # Запускаем планировщик
    start_scheduler()

    logger.info("Планировщик запущен. Ожидаем выполнение задач (7 секунд)...")
    logger.info("Нажмите Ctrl+C для выхода.")

    # Даем планировщику поработать 7 секунд
    try:
        await asyncio.sleep(7.0)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение прервано пользователем.")
