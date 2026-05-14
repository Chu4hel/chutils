import asyncio
import logging
import threading
from chutils import setup_logger, bind_context, clear_context

# Настройка логгера (по умолчанию используется текстовый формат с поддержкой контекста)
logger = setup_logger("context_example")

async def process_request(request_id: str, user: str):
    # Привязываем метаданные к текущему асинхронному контексту
    bind_context(req_id=request_id, user=user)
    
    logger.info("Начало обработки запроса")
    await asyncio.sleep(0.1)
    
    # Контекст сохраняется после await
    logger.info("Выполнение промежуточного этапа")
    
    # Можно доукомплектовать контекст
    bind_context(status="processing")
    logger.info("Запрос в процессе")
    
    # Очистка не обязательна для ContextVar (они изолированы), 
    # но полезна для чистоты в долгоживущих задачах
    clear_context()
    logger.info("Запрос завершен (контекст очищен)")

def thread_worker(name: str):
    bind_context(thread=name)
    logger.info(f"Привет из потока {name}")

async def main():
    print("--- Демонстрация асинхронной изоляции ---")
    # Запускаем две задачи параллельно. Их контексты не будут перемешиваться.
    await asyncio.gather(
        process_request("REQ-001", "alice"),
        process_request("REQ-002", "bob")
    )

    print("\n--- Демонстрация в потоках ---")
    t1 = threading.Thread(target=thread_worker, args=("Worker-1",))
    t2 = threading.Thread(target=thread_worker, args=("Worker-2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

if __name__ == "__main__":
    asyncio.run(main())
