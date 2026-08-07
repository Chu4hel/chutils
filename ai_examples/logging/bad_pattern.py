"""
Антипаттерн: Использование print, ручная настройка logging и утечка секретов.
"""

import logging

# Плохо: Ручная настройка логгера без учета стандартов проекта
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("my_app")


def process_transaction(user_id, token, amount):
    # Плохо: Использование print() для отладки. Логи не попадут в ротируемые файлы.
    print(f"Starting transaction for user {user_id}")

    # Плохо: Утечка секрета (token) в открытом виде в лог.
    # Плохо: Ручная сборка контекста (user_id передается в строке сообщения).
    logger.info(f"Processing transaction: user={user_id}, token={token}, amount={amount}")

    try:
        # Эмуляция логики
        result = amount / 0
    except Exception as e:
        # Плохо: Вывод только сообщения об ошибке без трассировки стека (stack trace).
        logger.error(f"Произошла ошибка при транзакции: {e}")
