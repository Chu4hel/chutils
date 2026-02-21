"""
Пример 7: Использование декоратора log_function_details

Этот пример показывает, как использовать декоратор `@log_function_details`
для автоматического логирования вызовов функций.
"""

from chutils.decorators import log_function_details
from chutils.logger import setup_logger, ChutilsLogger


def main():
    """
    Основная функция, демонстрирующая работу декоратора.
    """
    # 1. Настраиваем логгер.
    # Чтобы видеть вывод от декоратора, уровень лога должен быть DEVDEBUG.
    # В этом примере мы не используем config.yml, а задаем уровень явно.
    logger: ChutilsLogger = setup_logger(log_level="DEVDEBUG")

    logger.info("Логгер настроен. Сейчас будет вызвана декорированная функция.")

    # 2. Вызываем функцию, обернутую декоратором.
    result = decorated_sum(5, 10, option="fast")

    logger.info(f"Декорированная функция вернула результат: {result}")
    logger.info("Проверьте логи выше, чтобы увидеть детальную информацию от декоратора.")


@log_function_details
def decorated_sum(a: int, b: int, option: str = "default"):
    """
    Простая функция, которая суммирует два числа.
    Она обернута декоратором для логирования.
    """
    return a + b


if __name__ == "__main__":
    main()
