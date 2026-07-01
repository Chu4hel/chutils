import asyncio
import time

from chutils import setup_logger, provide, inject, Inject

# 1. Настраиваем логгер chutils
logger = setup_logger(name="di_example")


# 2. Регистрируем зависимости декларативно с помощью @provide
@provide()
class DatabaseService:
    def __init__(self) -> None:
        logger.info("Initializing DatabaseService (Singleton)...")
        self.connected = True

    def query(self, sql: str) -> str:
        return f"Result of '{sql}'"


@provide(scope="transient")
class RequestContext:
    def __init__(self) -> None:
        self.request_id = f"req-{int(time.time() * 1000)}"
        logger.info(f"Creating RequestContext (Transient) - {self.request_id}")


# 3. Рекурсивная зависимость (UserService зависит от DatabaseService)
@provide()
class UserService:
    def __init__(self, db: DatabaseService) -> None:
        logger.info("Initializing UserService (depends on DatabaseService)...")
        self.db = db

    def get_user_name(self, user_id: int) -> str:
        return self.db.query(f"SELECT name FROM users WHERE id = {user_id}")


# 4. Внедрение зависимостей через @inject и маркер Inject() в синхронную функцию
@inject()
def process_user_request(
        user_id: int,
        user_service: UserService = Inject(),
        ctx: RequestContext = Inject()
) -> None:
    logger.info(f"Processing request in {ctx.request_id} for user {user_id}")
    name = user_service.get_user_name(user_id)
    logger.info(f"User name: {name}")


# 5. Внедрение зависимостей в асинхронную функцию
@inject()
async def process_async_task(
        db: DatabaseService = Inject(),
        user_service: UserService = Inject()
) -> None:
    logger.info("Starting async background task...")
    await asyncio.sleep(0.1)
    result = db.query("SELECT COUNT(*) FROM sessions")
    logger.info(f"Async query completed. Active sessions: {result}")


async def main() -> None:
    logger.info("=== Dependency Injection Demonstration ===")

    # Вызываем функцию с авто-внедрением зависимостей
    process_user_request(101)

    # Повторный вызов демонстрирует, что UserService и DatabaseService - Singleton (не пересоздаются),
    # а RequestContext - Transient (создается новый объект для каждого запроса)
    process_user_request(102)

    # Вызываем асинхронную таску с инъекцией
    await process_async_task()


if __name__ == "__main__":
    asyncio.run(main())
