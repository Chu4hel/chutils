"""
Пример использования OpenTelemetry для распределенного трассирования.
Демонстрирует использование декоратора @trace и автоматическую корреляцию с логами.

Для работы примера желательно наличие установленного пакета:
pip install chutils[otel]
"""

import time

from chutils import setup_logger, setup_tracing, trace

# 1. Настройка трассировки
# В реальном приложении вы можете использовать exporter_type="otlp" для Jaeger/Zipkin.
# Здесь мы используем "console", чтобы увидеть результат прямо в терминале.
setup_tracing(service_name="example-service", exporter_type="console")

# 2. Настройка логгера (он автоматически будет подхватывать trace_id из контекста)
logger = setup_logger(log_level="INFO")


@trace(attributes={"module": "billing"})
def process_payment(amount: float):
    logger.info(f"Обработка платежа на сумму {amount}...")
    time.sleep(0.1)
    # Вызываем вложенную функцию
    validate_card("1234-5678")
    return True


@trace(capture_kwargs=True)
def validate_card(card_number: str):
    logger.info("Проверка валидности карты...")
    time.sleep(0.05)
    return True


def main():
    logger.info("Запуск основного процесса...")

    # Все логи внутри этой функции и вызываемых ею @trace функций 
    # будут иметь один и тот же trace_id.
    process_payment(99.99)

    logger.info("Процесс завершен.")


if __name__ == "__main__":
    main()
