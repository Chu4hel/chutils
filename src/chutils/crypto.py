"""Модуль для портативного детерминированного шифрования данных.

Предоставляет функции для шифрования строк и файлов с использованием
детерминированного ключа, сгенерированного на основе seed-пароля (алгоритм Fernet).
"""

import base64
import hashlib
from pathlib import Path

from chutils.exceptions import OptionalDependencyError

try:
    from cryptography.fernet import Fernet, InvalidToken

    _HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover
    # Оставляем заглушки для импорта, чтобы предотвратить AttributeError
    Fernet = None  # type: ignore
    InvalidToken = None  # type: ignore
    _HAS_CRYPTOGRAPHY = False

__all__ = ["encrypt_portable", "decrypt_portable", "encrypt_file", "decrypt_file"]


def _get_fernet_key(seed: str) -> bytes:
    """Генерирует детерминированный 32-байтный URL-safe Base64 ключ из seed-строки.

    Args:
        seed: Строка-пароль.

    Returns:
        Ключ в формате bytes, совместимый с Fernet.
    """
    hash_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(hash_bytes)


def encrypt_portable(data: str, seed: str) -> str:
    """Шифрует строку с использованием детерминированного ключа, полученного из seed.

    Args:
        data: Исходная строка для шифрования.
        seed: Строка-пароль для генерации ключа.

    Returns:
        Зашифрованная строка в формате Base64.

    Raises:
        OptionalDependencyError: Если библиотека cryptography не установлена.
    """
    if not _HAS_CRYPTOGRAPHY:
        raise OptionalDependencyError(
            "Для использования модуля crypto установите библиотеку:\n"
            "pip install chutils[crypto]"
        )

    key = _get_fernet_key(seed)
    f = Fernet(key)
    encrypted_bytes = f.encrypt(data.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_portable(encrypted_data: str, seed: str) -> str | None:
    """Дешифрует строку с использованием детерминированного ключа, полученного из seed.

    Args:
        encrypted_data: Зашифрованная строка в формате Base64.
        seed: Строка-пароль для генерации ключа.

    Returns:
        Расшифрованная строка или None, если дешифрование завершилось ошибкой.

    Raises:
        OptionalDependencyError: Если библиотека cryptography не установлена.
    """
    if not _HAS_CRYPTOGRAPHY:
        raise OptionalDependencyError(
            "Для использования модуля crypto установите библиотеку:\n"
            "pip install chutils[crypto]"
        )

    key = _get_fernet_key(seed)
    f = Fernet(key)
    try:
        decrypted_bytes = f.decrypt(encrypted_data.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except (InvalidToken, Exception):
        return None


def encrypt_file(
        file_path: str | Path,
        seed: str,
        output_path: str | Path | None = None
) -> Path:
    """Шифрует содержимое файла и сохраняет результат.

    Args:
        file_path: Путь к исходному файлу.
        seed: Строка-пароль для генерации ключа.
        output_path: Путь для сохранения результата. Если не указан,
            исходный файл перезаписывается.

    Returns:
        Путь к зашифрованному файлу.

    Raises:
        OptionalDependencyError: Если библиотека cryptography не установлена.
    """
    if not _HAS_CRYPTOGRAPHY:
        raise OptionalDependencyError(
            "Для использования модуля crypto установите библиотеку:\n"
            "pip install chutils[crypto]"
        )

    fp = Path(file_path)
    out_p = Path(output_path) if output_path is not None else fp

    data_bytes = fp.read_bytes()
    key = _get_fernet_key(seed)
    f = Fernet(key)
    encrypted_bytes = f.encrypt(data_bytes)
    out_p.write_bytes(encrypted_bytes)
    return out_p


def decrypt_file(
        file_path: str | Path,
        seed: str,
        output_path: str | Path | None = None
) -> bool:
    """Дешифрует содержимое файла и сохраняет результат.

    Args:
        file_path: Путь к зашифрованному файлу.
        seed: Строка-пароль для генерации ключа.
        output_path: Путь для сохранения результата. Если не указан,
            файл перезаписывается.

    Returns:
        True, если дешифрование прошло успешно, иначе False.

    Raises:
        OptionalDependencyError: Если библиотека cryptography не установлена.
    """
    if not _HAS_CRYPTOGRAPHY:
        raise OptionalDependencyError(
            "Для использования модуля crypto установите библиотеку:\n"
            "pip install chutils[crypto]"
        )

    fp = Path(file_path)
    out_p = Path(output_path) if output_path is not None else fp

    try:
        encrypted_bytes = fp.read_bytes()
        key = _get_fernet_key(seed)
        f = Fernet(key)
        decrypted_bytes = f.decrypt(encrypted_bytes)
        out_p.write_bytes(decrypted_bytes)
        return True
    except (InvalidToken, Exception):
        return False
