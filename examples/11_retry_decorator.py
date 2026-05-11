"""
Пример использования декоратора @retry для автоматического повтора функций.

Этот пример демонстрирует, как использовать декоратор @retry для обработки
нестабильных операций (например, сетевых запросов), которые могут завершаться ошибкой.
"""

import asyncio
import random

from chutils.decorators import retry
from chutils.logger import setup_logger

# Настраиваем логгер, чтобы видеть сообщения о повторах
logger = setup_logger("retry_example")


# --- 1. Синхронный пример ---

@retry(retries=3, delay=1.0, backoff=2.0, jitter=True)
def unstable_sync_operation():
    """Синхронная функция, которая иногда падает."""
    print("  [Sync] Попытка выполнения...")
    if random.random() < 0.7:
        raise ConnectionError("Сетевой сбой в синхронном коде")
    return "Синхронный успех!"


# --- 2. Асинхронный пример ---

@retry(retries=5, delay=0.5, backoff=1.5, exceptions=(ValueError,))
async def unstable_async_operation():
    """Асинхронная функция с фильтрацией исключений."""
    print("  [Async] Попытка выполнения...")
    if random.random() < 0.8:
        raise ValueError("Ошибка данных в асинхронном коде")
    return "Асинхронный успех!"


async def main():
    print("--- Тестирование синхронного декоратора ---")
    try:
        result = unstable_sync_operation()
        print(f"Результат: {result}")
    except Exception as e:
        print(f"Операция не удалась после всех попыток: {e}")

    print("\n--- Тестирование асинхронного декоратора ---")
    try:
        result = await unstable_async_operation()
        print(f"Результат: {result}")
    except Exception as e:
        print(f"Операция не удалась после всех попыток: {e}")


if __name__ == "__main__":
    asyncio.run(main())
