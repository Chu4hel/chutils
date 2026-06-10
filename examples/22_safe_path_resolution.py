"""
Пример 22: Безопасное разрешение путей и предотвращение Path Traversal.

Этот пример демонстрирует использование функции `resolve_safe_path` и класса
исключения `PathTraversalError` для безопасной работы с файловой системой при
обработке путей, переданных из внешних или ненадежных источников.
"""

from pathlib import Path

from chutils.exceptions import PathTraversalError
from chutils.fs import resolve_safe_path
from chutils.logger import setup_logger, LogLevel

# Настраиваем логгер для вывода результатов
logger = setup_logger("safe_path_demo", log_level=LogLevel.INFO)


def read_user_file(user_provided_path: str, base_directory: Path) -> str:
    """
    Безопасно считывает файл, переданный пользователем.
    
    Использует `resolve_safe_path`, чтобы гарантировать, что пользователь
    не сможет выйти за пределы разрешенной директории (base_directory).
    """
    try:
        # Безопасно разрешаем путь относительно базовой директории
        safe_path = resolve_safe_path(user_provided_path, base_dir=base_directory)

        # Если путь безопасен, считываем файл
        if safe_path.exists() and safe_path.is_file():
            content = safe_path.read_text(encoding="utf-8")
            return content
        else:
            return "[ОШИБКА] Файл не найден."

    except PathTraversalError as e:
        # Логируем попытку обхода пути и возвращаем предупреждение
        logger.error(
            "Попытка Path Traversal! Пользователь запросил: '%s', "
            "попытка выхода за пределы базы: '%s'",
            e.context.get("attempted_path"), e.context.get("base_path")
        )
        return f"[ОШИБКА БЕЗОПАСНОСТИ] Доступ запрещен: {e}"


def main() -> None:
    # 1. Подготовка демонстрационной директории
    demo_base = Path("./demo_sandbox").resolve()
    demo_base.mkdir(exist_ok=True)

    # Создаем тестовый файл внутри песочницы
    allowed_file = demo_base / "report.txt"
    allowed_file.write_text("Конфиденциальные данные отчета: Успешные продажи 2026!", encoding="utf-8")

    # Создаем секретный файл ВНЕ песочницы (на уровень выше)
    secret_file = demo_base.parent / "super_secret.txt"
    secret_file.write_text("СЕКРЕТНЫЙ КЛЮЧ: 42-42-42", encoding="utf-8")

    logger.info("Базовая директория песочницы: %s", demo_base)

    print("\n--- Сценарий 1: Запрос легитимного файла ---")
    # Передаем обычное имя файла
    content_normal = read_user_file("report.txt", base_directory=demo_base)
    print(f"Содержимое файла: {content_normal}")

    print("\n--- Сценарий 2: Попытка атаки Path Traversal (выход вверх) ---")
    # Передаем относительный путь с выходом наружу песочницы
    content_traversal = read_user_file("../super_secret.txt", base_directory=demo_base)
    print(f"Результат чтения: {content_traversal}")

    print("\n--- Сценарий 3: Попытка доступа по абсолютному пути вне песочницы ---")
    # Пытаемся передать абсолютный путь к секретному файлу
    absolute_secret_path = str(secret_file.resolve())
    content_absolute = read_user_file(absolute_secret_path, base_directory=demo_base)
    print(f"Результат чтения: {content_absolute}")

    # Уборка
    if allowed_file.exists():
        allowed_file.unlink()
    if secret_file.exists():
        secret_file.unlink()
    if demo_base.exists():
        demo_base.rmdir()


if __name__ == "__main__":
    main()
