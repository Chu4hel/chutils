import asyncio
import time

from chutils import setup_logger
from chutils.metrics import increment, set_gauge, observe, timer, generate_latest, get_provider

logger = setup_logger(name="metrics_example")


# 1. Замер времени выполнения синхронной функции с помощью декоратора @timer
@timer("process_item_duration_seconds", labels={"type": "sync"})
def process_item_sync(item_id: int) -> None:
    logger.info(f"Начало обработки элемента {item_id}...")
    time.sleep(0.05)  # Имитируем работу
    logger.info(f"Элемент {item_id} обработан.")


# 2. Замер времени выполнения асинхронной функции с помощью декоратора @timer
@timer("process_item_duration_seconds", labels={"type": "async"})
async def process_item_async(item_id: int) -> None:
    logger.info(f"Начало асинхронной обработки элемента {item_id}...")
    await asyncio.sleep(0.08)  # Имитируем асинхронное ожидание
    logger.info(f"Асинхронный элемент {item_id} обработан.")


async def main() -> None:
    logger.info("=== Демонстрация модуля chutils.metrics ===")

    # Показываем, какой провайдер активен
    provider = get_provider()
    logger.info(f"Активный провайдер метрик: {provider.__class__.__name__}")

    # 3. Использование счетчиков (Counters)
    logger.info("Увеличиваем счетчик обработанных запросов...")
    increment("http_requests_total", 1.0, {"method": "GET", "endpoint": "/api/v1/users", "status": "200"})
    increment("http_requests_total", 1.0, {"method": "POST", "endpoint": "/api/v1/login", "status": "201"})
    increment("http_requests_total", 1.0, {"method": "GET", "endpoint": "/api/v1/users", "status": "200"})

    # 4. Использование датчиков (Gauges)
    logger.info("Устанавливаем значение датчика активных сессий...")
    set_gauge("active_sessions", 15.0, {"zone": "eu-west"})
    set_gauge("active_sessions", 42.0, {"zone": "us-east"})

    # 5. Использование гистограмм (Histograms / Timers) вручную
    logger.info("Записываем размер полезной нагрузки...")
    observe("request_payload_bytes", 512.0, {"client": "mobile"})
    observe("request_payload_bytes", 2048.0, {"client": "web"})

    # Вызов синхронной функции с таймером
    process_item_sync(101)

    # Вызов асинхронной функции с таймером
    await process_item_async(202)

    # Использование таймера как контекстного менеджера
    logger.info("Замеряем блок кода через контекстный менеджер...")
    with timer("db_query_duration_seconds", labels={"query": "select_users"}):
        time.sleep(0.03)  # Имитируем запрос к БД

    # 6. Генерация дампа метрик
    logger.info("Генерируем текстовый отчет по метрикам в формате Prometheus:")
    metrics_report = generate_latest()
    print("\n" + "=" * 50)
    print(metrics_report.strip())
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
