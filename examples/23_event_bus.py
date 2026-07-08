"""
Пример 23: Использование In-Memory Event Bus (Шины событий).

Демонстрирует возможности регистрации обработчиков (подписчиков) на события
и публикации событий как в синхронном, так и в асинхронном контекстах.
Также показывает работу со стратегиями обработки ошибок и Pydantic-моделями.
"""

import asyncio

from chutils.events import subscribe, publish, publish_async, ErrorStrategy, EventBus
from chutils.exceptions import EventBusExceptionGroup
from chutils.logger import setup_logger

# Инициализируем стандартный логгер библиотеки
logger = setup_logger("event_bus_demo")

# Опциональный импорт Pydantic
try:
    import pydantic


    class UserCreatedEvent(pydantic.BaseModel):
        user_id: int
        username: str
        email: str


    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


# 1. Регистрация синхронного обработчика
@subscribe("user_registered")
def send_welcome_email(user_id: int, username: str, **kwargs) -> None:
    logger.info(
        "[Sync Handler] Отправка приветственного письма для %s (ID: %d)",
        username,
        user_id,
    )


# 2. Регистрация асинхронного обработчика
@subscribe("user_registered")
async def initialize_user_workspace(user_id: int, username: str, **kwargs) -> None:
    logger.info("[Async Handler] Начало инициализации воркспейса для %s...", username)
    await asyncio.sleep(0.1)  # Имитация асинхронного ввода-вывода
    logger.info(
        "[Async Handler] Воркспейс для %s (ID: %d) успешно настроен!", username, user_id
    )


# 3. Обработчик, использующий Pydantic
if HAS_PYDANTIC:
    @subscribe("user_created_model")
    def log_user_model(event: UserCreatedEvent) -> None:
        logger.info(
            "[Pydantic Handler] Создан пользователь: %s (Email: %s)",
            event.username,
            event.email,
        )


async def async_main() -> None:
    logger.info("=== 1. Синхронная публикация (publish) ===")
    # Синхронный publish запускается из любого места.
    # Синхронные обработчики выполняются немедленно в текущем потоке.
    # Асинхронные обработчики запускаются в фоновом event loop в отдельном потоке.
    publish("user_registered", user_id=42, username="Иван")

    # Подождем немного, так как асинхронный обработчик в publish выполняется в фоне
    await asyncio.sleep(0.2)

    logger.info("\n=== 2. Асинхронная публикация (publish_async) ===")
    # Асинхронный publish_async ждет выполнения ВСЕХ подписчиков (и sync, и async).
    # Синхронные обработчики выполняются параллельно в пуле потоков.
    await publish_async("user_registered", user_id=100, username="Алексей")

    if HAS_PYDANTIC:
        logger.info("\n=== 3. Публикация с Pydantic Model Payload ===")
        event_obj = UserCreatedEvent(
            user_id=999, username="Светлана", email="svetlana@example.com"
        )
        publish("user_created_model", event_obj)

    logger.info("\n=== 4. Демонстрация стратегий обработки ошибок ===")
    # Создадим отдельный локальный инстанс шины для демонстрации ошибок
    error_bus = EventBus(error_strategy=ErrorStrategy.COLLECT)

    @error_bus.subscribe("data_sync")
    def faulty_handler_1():
        raise ValueError("Сбой при выгрузке данных")

    @error_bus.subscribe("data_sync")
    def faulty_handler_2():
        raise OSError("Ошибка сети при синхронизации")

    logger.info("Вызываем шину с ErrorStrategy.COLLECT (собрать все ошибки):")
    try:
        error_bus.publish("data_sync")
    except EventBusExceptionGroup as e:
        logger.error("Перехвачена группа ошибок (совместимый перехват):")
        for exc in e.exceptions:
            logger.error(" - %s: %s", type(exc).__name__, exc)

    # На Python >= 3.11 вы также можете использовать стандартный синтаксис except*:
    # try:
    #     error_bus.publish("data_sync")
    # except* ValueError as eg:
    #     logger.error("Обработан ValueError из группы: %s", eg.exceptions)
    # except* OSError as eg:
    #     logger.error("Обработан OSError из группы: %s", eg.exceptions)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
