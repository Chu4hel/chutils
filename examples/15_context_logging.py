"""
Пример использования контекстного логирования в chutils.

ДЛЯ ЧЕГО ЭТО НУЖНО:
В асинхронных приложениях (FastAPI, asyncio) или многопоточных серверах бывает трудно 
отследить путь конкретного запроса через множество функций. Контекстное логирование 
позволяет один раз "привязать" метаданные (например, request_id или user_id) в начале 
обработки, и они будут автоматически добавляться во все логи, вызванные внутри этой 
цепочки выполнения, даже если они находятся в других модулях или глубоко во вложенных функциях.

КАК ЭТО РАБОТАЕТ:
Используется механизм Python `contextvars`. Он гарантирует, что данные "изолированы": 
корутина А не увидит данные корутины Б, даже если они работают параллельно в одном потоке.
"""

import asyncio
import threading

from chutils import setup_logger, bind_context, clear_context

# Настройка логгера. setup_logger автоматически подключает ContextFilter.
logger = setup_logger("context_example")


async def sub_task(name: str):
    # Эта функция не принимает request_id явно, но он появится в логах автоматически!
    logger.info(f"Выполнение подзадачи для {name}")


async def process_request(request_id: str, user: str):
    # 1. Привязываем метаданные к текущему асинхронному контексту.
    # Теперь каждый лог в этой корутине будет содержать эти данные.
    bind_context(req=request_id, user=user)

    logger.info("Начало обработки запроса")
    # Ожидаемый вывод (текст): ... [req=REQ-001 user=alice] Начало обработки запроса

    await asyncio.sleep(0.1)

    # Контекст сохраняется после await (переключаемся на другую задачу и обратно)
    await sub_task(user)

    # 2. Можно "доукомплектовать" контекст новыми данными в процессе
    bind_context(stage="database")
    logger.info("Работа с базой данных")
    # Ожидаемый вывод: ... [req=REQ-001 user=alice stage=database] Работа с базой данных

    # 3. Очистка контекста. Полезна в Celery или при переиспользовании воркеров.
    clear_context()
    logger.info("Контекст очищен")
    # Ожидаемый вывод: ... [] Контекст очищен


def thread_worker(name: str):
    # В потоках контекст тоже изолирован
    bind_context(thread=name)
    logger.info("Привет из отдельного потока")
    # Ожидаемый вывод: ... [thread=Worker-1] Привет из отдельного потока


async def main():
    print("--- ДЕМОНСТРАЦИЯ АСИНХРОННОЙ ИЗОЛЯЦИИ ---")
    print("Запускаем две задачи параллельно. Метаданные не перемешаются.\n")

    # Запускаем две задачи параллельно. 
    # Благодаря ContextVar, alice никогда не увидит REQ-002 в своих логах.
    await asyncio.gather(
        process_request("REQ-001", "alice"),
        process_request("REQ-002", "bob")
    )

    print("\n--- ДЕМОНСТРАЦИЯ В ПОТОКАХ ---")
    t1 = threading.Thread(target=thread_worker, args=("Worker-1",))
    t2 = threading.Thread(target=thread_worker, args=("Worker-2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    print("\n--- JSON ФОРМАТ ---")
    print("Если включить json_format=True, контекст попадет в отдельное поле 'context':")
    print('{"message": "Начало...", "context": {"req": "REQ-001", "user": "alice"}, ...}')

    print("\n--- ИНТЕГРАЦИЯ С OPENTELEMETRY ---")
    print("Если вы используете @trace или setup_tracing(), в логи автоматически")
    print("добавятся поля 'trace_id' и 'span_id', коррелирующие с вашими трассами.")


if __name__ == "__main__":
    asyncio.run(main())
