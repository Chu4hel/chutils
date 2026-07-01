"""
Пример 27: Ограничение частоты запросов (Rate Limiting).

Демонстрирует использование декоратора `@rate_limit` для синхронных и асинхронных функций,
различные стратегии (Token Bucket, Leaky Bucket), блокировку выполнения и работу с ключами.
"""

import asyncio
import time

from chutils import rate_limit, RateLimitExceededError, setup_logger

logger = setup_logger("rate_limiting_example")


# 1. Синхронная функция с ограничением по умолчанию (Token Bucket, Fail Fast)
@rate_limit(max_calls=3, period=2.0, strategy="token_bucket", wait=False)
def sync_api_call(user_id: int) -> None:
    logger.info(f"[Sync API] Вызов от пользователя {user_id}")


# 2. Асинхронная функция с ожиданием (Wait)
@rate_limit(max_calls=2, period=1.0, strategy="leaky_bucket", wait=True)
async def async_api_call(ip: str) -> None:
    logger.info(f"[Async API] Вызов с IP-адреса {ip}")


# 3. Динамический ключ ограничения на основе аргументов (Key Function)
@rate_limit(
    max_calls=1,
    period=2.0,
    key_func=lambda method, path: f"route_{method}_{path}",
    wait=False
)
def handle_request(method: str, path: str) -> None:
    logger.info(f"[Route API] Запрос {method} {path} выполнен")


async def main() -> None:
    logger.info("=== 1. Синхронные вызовы (Fail Fast) ===")
    logger.info("Разрешено 3 вызова за 2 секунды.")

    # Первые 3 вызова пройдут успешно
    for i in range(3):
        sync_api_call(101)

    # 4-й вызов сразу выбросит RateLimitExceededError
    try:
        sync_api_call(101)
    except RateLimitExceededError as e:
        logger.warning(f"Превышен лимит вызовов: {e}")

    logger.info("\n=== 2. Асинхронные вызовы с ожиданием (Wait/Smoothing) ===")
    logger.info("Разрешено 2 вызова за 1 секунду. Остальные будут плавно ожидать.")

    start_time = time.monotonic()
    tasks = [async_api_call("192.168.1.1") for _ in range(5)]
    await asyncio.gather(*tasks)
    elapsed = time.monotonic() - start_time
    logger.info(f"Выполнение 5 вызовов заняло {elapsed:.2f} секунд.")

    logger.info("\n=== 3. Динамические ключи лимитирования ===")
    logger.info("Разрешен 1 вызов на один роут за 2 секунды.")

    # Эти вызовы используют разные ключи, поэтому пройдут успешно
    handle_request("GET", "/users")
    handle_request("POST", "/login")

    # А этот вызов повторный для /users и упадет по лимиту
    try:
        handle_request("GET", "/users")
    except RateLimitExceededError as e:
        logger.warning(f"Превышен лимит для GET /users: {e}")


if __name__ == "__main__":
    asyncio.run(main())
