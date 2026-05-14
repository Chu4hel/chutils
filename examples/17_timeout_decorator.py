"""
Пример использования декоратора @timeout.

Этот пример демонстрирует, как ограничить время выполнения функции,
как использовать резервное значение (fallback) и как комбинировать его с @retry.
"""

import asyncio
import time

from chutils import timeout, retry


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

    print("\n--- Пример 3: Совместное использование @retry и @timeout ---")
    call_count = 0

    @retry(retries=2, delay=0.5)
    @timeout(0.5)
    def fluky_slow_function():
        nonlocal call_count
        call_count += 1
        print(f"Попытка {call_count}: начинаю работу...")
        if call_count < 3:
            time.sleep(1.0)  # Будет таймаут на первых двух попытках
        return "Успех на третьей попытке!"

    try:
        final_result = fluky_slow_function()
        print(f"Итоговый результат: {final_result}")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")


if __name__ == "__main__":
    main()
