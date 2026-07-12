"""
Антипаттерн: Перехват RuntimeError вместо OptionalDependencyError (устарело в v3.0.0).
"""

import os


def use_encryption(data: str) -> str:
    """Шифрует данные — устаревший подход к обработке опциональных зависимостей."""
    try:
        # Импорт опциональной зависимости напрямую
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        f = Fernet(key)
        return f.encrypt(data.encode()).decode()
    except ImportError:
        # Плохо (устарело до v3.0.0): Перехват ImportError вместо OptionalDependencyError.
        # Вызывающий код не знает, что это опциональная зависимость chutils.
        # Нет hint'а с командой установки.
        print("cryptography не установлен, шифрование недоступно")
        return data
    except RuntimeError as e:
        # Плохо (до v3.0.0): RuntimeError использовался для отсутствия зависимостей.
        # В v3.0.0 он заменён на OptionalDependencyError — этот перехват больше не сработает.
        print(f"Ошибка: {e}")
        return data


def use_text_similarity(a: str, b: str) -> bool:
    """Сравнивает строки — устаревший подход."""
    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(a, b) > 90
    except (ImportError, RuntimeError):
        # Плохо: Нет информации для пользователя о том, как установить зависимость.
        return a == b


def check_env() -> None:
    # Плохо: Ручная проверка переменной окружения вместо chutils.env
    if os.getenv("OTEL_ENABLED"):
        try:
            import opentelemetry  # noqa: F401
        except ImportError:
            # Плохо: RuntimeError бросается вместо OptionalDependencyError (v3.0.0+)
            raise RuntimeError("opentelemetry не установлен")
