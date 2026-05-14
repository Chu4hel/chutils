"""
Пример использования декоратора @timeout.

Этот пример демонстрирует, как ограничить время выполнения функции
и как использовать резервное значение (fallback).
"""

import time
import asyncio
from chutils import timeout


# 1. Синхронная функция с таймаутом
@timeout(1.0)
def slow_sync_function():
    print("Синхронная функция: начинаю долгую работу...")
    time.sleep(2.0)
    return "Работа завершена"


# 2. Асинхронная функция с таймаутом и fallback
@timeout(0.5, fallback="Стандартный результат")
async def slow_async_function():
    print("Асинхронная функция: начинаю долгую работу...")
    await asyncio.sleep(1.0)
    return "Работа завершена успешно"


def main():
    print("--- Пример 1: Синхронный таймаут (без fallback) ---")
    try:
        slow_sync_function()
    except TimeoutError as e:
        print(f"Поймали ожидаемую ошибку: {e}")

    print("\n--- Пример 2: Асинхронный таймаут (с fallback) ---")
    result = asyncio.run(slow_async_function())
    print(f"Результат асинхронной функции: {result}")


if __name__ == "__main__":
    main()
