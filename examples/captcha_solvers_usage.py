"""Пример использования модуля chutils.scraping.captcha для интеграции с решателями капчи.

Демонстрирует:
1. Синхронное и асинхронное решение текстовых капч по картинке.
2. Синхронное и асинхронное решение ReCaptcha v2.
3. Автоматическое извлечение API-ключей из SecretManager.
"""

import asyncio

from chutils.scraping.captcha import (
    RuCaptchaSolver,
    AsyncAntiCaptchaSolver,
    CaptchaError,
)


def run_sync_example() -> None:
    print("=== 1. Синхронный пример (RuCaptcha) ===")

    # 1. Загрузка ключа произойдет автоматически из secret_manager по ключу RUCAPTCHA_API_KEY.
    # Если вы хотите передать ключ явно: solver = RuCaptchaSolver(api_key="your_api_key")
    # В данном примере передаем фиктивный ключ для демонстрации.
    try:
        solver = RuCaptchaSolver(api_key="demo_api_key")

        # Решение текстовой капчи по картинке (передаем бинарные данные)
        dummy_image = b"GIF89a..."  # Имитация байтов картинки
        print("Отправка картинки на решение...")
        # Уменьшим таймаут и интервал опроса для примера, чтобы не зависать
        # (в реальном коде используются дефолтные значения)
        result = solver.solve_image(dummy_image, timeout=10.0, poll_interval=1.0)
        print(f"Результат решения капчи: {result}")

    except CaptchaError as e:
        print(f"Ошибка при решении капчи: {e}")
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")


async def run_async_example() -> None:
    print("\n=== 2. Асинхронный пример (Anti-Captcha) ===")

    try:
        # Автоматически ищет ANTICAPTCHA_API_KEY в secret_manager.
        # Передаем демонстрационный ключ явно.
        async_solver = AsyncAntiCaptchaSolver(api_key="demo_api_key")

        print("Асинхронная отправка ReCaptcha v2...")
        token = await async_solver.solve_recaptcha(
            sitekey="6LeOeSkUAAAAACl2pxhXLD37t3h7wJz16F8ySU73",
            page_url="https://rucaptcha.com/demo/recaptcha-v2",
            timeout=15.0,
            poll_interval=2.0
        )
        print(f"Полученный ReCaptcha-токен: {token[:30]}...")

    except CaptchaError as e:
        print(f"Ошибка асинхронного решения: {e}")


if __name__ == "__main__":
    # Запускаем синхронный пример
    run_sync_example()

    # Запускаем асинхронный пример
    asyncio.run(run_async_example())
