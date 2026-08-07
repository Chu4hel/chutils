"""
Паттерн: Использование chutils.setup_logger, контекста и безопасного логирования.
"""

from __future__ import annotations

from chutils import setup_logger, bind_context

# Инициализируем настроенный логгер библиотеки chutils
logger = setup_logger(name="transaction_service")


def process_transaction(user_id: str, token: str, amount: float) -> None:
    """Обрабатывает финансовую транзакцию пользователя.

    Args:
        user_id: Уникальный идентификатор пользователя.
        token: Секретный токен авторизации (будет автоматически замаскирован).
        amount: Сумма транзакции.
    """
    # 1. Привязываем контекст (все логи внутри блока with получат extra поля автоматически)
    with bind_context(user_id=user_id, action="process_transaction"):
        # Хорошо: Ленивое форматирование логов (передаем параметры как extra/args)
        logger.info("Начало обработки транзакции на сумму: %s", amount)

        # Хорошо: Токен будет автоматически замаскирован в логгере chutils,
        # так как имя переменной содержит "token" или маскируется по маске.
        # Рекомендуется избегать логирования токенов вообще, но если это необходимо:
        logger.info("Авторизация транзакции: token=%s, amount=%s", token, amount)

        try:
            # Эмуляция выполнения логики
            raise ZeroDivisionError("Сбой шлюза оплаты")
        except ZeroDivisionError as e:
            # Хорошо: Использование logger.exception автоматически добавляет
            # полный traceback ошибки в лог, что критично для отладки.
            logger.exception("Ошибка при выполнении транзакции")
            raise
