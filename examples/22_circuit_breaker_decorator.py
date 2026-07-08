"""Пример 22: Использование декоратора @circuit_breaker (Предохранитель).

Демонстрирует, как защитить вызовы к внешним API от каскадных сбоев,
автоматически блокируя запросы в случае серии ошибок.
"""

import asyncio

from chutils.decorators import circuit_breaker
from chutils.exceptions import CircuitBreakerOpenError
from chutils.logger import setup_logger

logger = setup_logger("circuit_breaker_demo")


# 1. Синхронная функция, защищенная предохранителем
@circuit_breaker(failure_threshold=3, recovery_timeout=5)
def call_external_api(url: str, fail: bool = False) -> str:
    logger.info("Вызов API: %s", url)
    if fail:
        raise ConnectionError("Сбой сети")
    return "Ответ от API: OK"


# 2. Асинхронная корутина, защищенная предохранителем
@circuit_breaker(failure_threshold=2, recovery_timeout=4)
async def call_external_api_async(url: str, fail: bool = False) -> str:
    logger.info("Асинхронный вызов API: %s", url)
    await asyncio.sleep(0.05)
    if fail:
        raise ConnectionError("Асинхронный сбой сети")
    return "Асинхронный ответ от API: OK"


async def main() -> None:
    logger.info("=== 1. Тестирование синхронного Circuit Breaker ===")

    # Успешный запрос
    res = call_external_api("http://api.example.com/data")
    logger.info("Успешный результат: %s\n", res)

    # Инициируем 3 сбоя подряд для открытия цепи
    logger.info("Делаем 3 сбойных запроса:")
    for i in range(1, 4):
        try:
            call_external_api("http://api.example.com/data", fail=True)
        except ConnectionError as e:
            logger.warning("  Попытка %d: перехвачена ожидаемая ошибка: %s", i, e)

    # Четвертый вызов будет заблокирован предохранителем (цепь разомкнута - OPEN)
    logger.info("\nДелаем четвертый вызов (цепь должна быть OPEN):")
    try:
        call_external_api("http://api.example.com/data")
    except CircuitBreakerOpenError as e:
        logger.error("  [OK] Запрос заблокирован предохранителем: %s", e)

    # Подождем 6 секунд (recovery_timeout = 5) для перехода в Half-Open
    logger.info("\nЖдем 6 секунд для восстановления предохранителя...")
    await asyncio.sleep(6)

    # Теперь цепь в состоянии HALF_OPEN, следующий запрос должен пройти
    logger.info("Выполняем запрос после ожидания (Half-Open -> Closed):")
    res = call_external_api("http://api.example.com/data", fail=False)
    logger.info("Успешный результат восстановления: %s\n", res)

    logger.info("=== 2. Тестирование асинхронного Circuit Breaker ===")

    # 2 сбоя для открытия цепи
    for i in range(1, 3):
        try:
            await call_external_api_async("http://async.example.com/data", fail=True)
        except ConnectionError as e:
            logger.warning("  Async Попытка %d: %s", i, e)

    # Запрос заблокирован
    try:
        await call_external_api_async("http://async.example.com/data")
    except CircuitBreakerOpenError as e:
        logger.error("  [OK] Асинхронный запрос заблокирован: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
