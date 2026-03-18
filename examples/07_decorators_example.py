"""
Пример 7: Использование декоратора логирования функций.

Демонстрирует, как автоматически логировать аргументы, время выполнения
и результат функции с помощью @log_function_details.
Это избавляет от необходимости писать print() или logger.info() вручную в каждой функции.
"""

from chutils.decorators import log_function_details
from chutils.logger import setup_logger, ChutilsLogger, LogLevel


@log_function_details
def calculate_complex_logic(a: int, b: int, factor: float = 1.0) -> float:
    """Функция, детали вызова которой мы хотим видеть в логах."""
    import time
    time.sleep(0.1)  # Имитация работы
    return (a + b) * factor


def main() -> None:
    """
    Настраивает логгер и вызывает декорированную функцию.
    """
    # ВНИМАНИЕ: Декоратор логирует на уровне DEVDEBUG.
    # Чтобы увидеть вывод, установите соответствующий уровень логгера.
    logger: ChutilsLogger = setup_logger("decorator_demo", log_level=LogLevel.DEVDEBUG)

    logger.info("--- Вызов декорированной функции ---")

    # При вызове в консоли (и файле) появится:
    # 1. Какие аргументы были переданы.
    # 2. Сколько времени заняло выполнение.
    # 3. Что функция вернула в итоге.
    result: float = calculate_complex_logic(10, 20, factor=1.5)

    logger.info("Результат в основном коде: %.2f", result)


if __name__ == "__main__":
    main()
