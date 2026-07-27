"""
Пример использования модуля chutils.scraping.concurrency.

Демонстрирует организацию очереди задач скрапинга, лимитирование частоты
запросов по доменам и работу пула параллельных воркеров.
"""

import asyncio
from chutils.scraping.concurrency import (
    DomainRateLimiter,
    InMemoryTaskQueue,
    ScrapingTask,
    WorkerPool,
)


async def main() -> None:
    # 1. Создаем очередь задач
    queue = InMemoryTaskQueue()

    # Добавляем задачи с разным приоритетом и доменами
    await queue.push(ScrapingTask(url="https://ru.wikipedia.org/wiki/Python", priority=5))
    await queue.push(ScrapingTask(url="https://en.wikipedia.org/wiki/Asyncio", priority=10))
    await queue.push(ScrapingTask(url="https://example.com/api/data", priority=1))

    # 2. Настраиваем лимитер задержек по доменам
    limiter = DomainRateLimiter(
        default_delay=0.5,
        domain_rules={
            "*.wikipedia.org": 1.0,
        },
        max_domain_concurrency={
            "example.com": 2,
        },
    )

    # 3. Определяем функцию-обработчик
    async def process_task(task: ScrapingTask) -> None:
        print(f"[Worker] Выполнение задачи: {task.url} (приоритет: {task.priority})")
        await asyncio.sleep(0.1)

    # 4. Запускаем пул воркеров
    pool = WorkerPool(queue=queue, handler=process_task, limiter=limiter, max_workers=3)
    await pool.run_until_complete()

    print(f"Все задачи завершены! Успешно: {pool.completed_count}, Ошибок: {pool.failed_count}")


if __name__ == "__main__":
    asyncio.run(main())
