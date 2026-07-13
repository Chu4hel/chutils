"""
Паттерн: Правильная работа с опциональными зависимостями (v3.0.0+).

Демонстрирует:
- Перехват OptionalDependencyError вместо RuntimeError/ImportError
- Использование e.hint для вывода команды установки
- Graceful degradation для некритичных функций
- Fail-fast для критичных функций
"""

from __future__ import annotations

from chutils.exceptions import OptionalDependencyError


def use_encryption_safe(data: str) -> str:
    """Шифрует данные с изящной деградацией при отсутствии зависимости.

    Args:
        data: Строка для шифрования.

    Returns:
        Зашифрованная строка или оригинал, если зависимость отсутствует.
    """
    try:
        from chutils.crypto import encrypt_portable
        return encrypt_portable(data, seed="project_seed")
    except OptionalDependencyError as e:
        # Хорошо: OptionalDependencyError содержит e.hint с командой установки.
        # Вызывающий код получает внятное объяснение, а не голый ImportError.
        print(f"[WARNING] Шифрование недоступно: {e.message}")
        print(f"[HINT] {e.hint}")  # например: "pip install chutils[crypto]"
        return data


def use_text_similarity_strict(a: str, b: str) -> bool:
    """Сравнивает строки с жёстким требованием зависимости.

    Args:
        a: Первая строка.
        b: Вторая строка.

    Returns:
        True, если строки похожи.

    Raises:
        OptionalDependencyError: Если rapidfuzz не установлен.
    """
    from chutils.text import is_significant_difference
    # Хорошо: Если rapidfuzz не установлен — OptionalDependencyError с подсказкой.
    # Не перехватываем — пусть вызывающий код решает, как обработать.
    return not is_significant_difference(a, b)


def setup_tracing_optional() -> None:
    """Инициализирует трассировку, если OpenTelemetry доступен.

    При отсутствии зависимости выводит предупреждение и продолжает работу.
    """
    try:
        from chutils.tracing import setup_tracing
        setup_tracing(service_name="my_app")
    except OptionalDependencyError as e:
        # Хорошо: Трассировка некритична — деградируем с подсказкой.
        print(f"[INFO] Трассировка недоступна: {e.hint}")
