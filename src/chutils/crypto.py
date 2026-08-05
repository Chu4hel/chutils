"""Модуль для портативного детерминированного шифрования данных.

Предоставляет функции для шифрования строк и файлов с использованием
детерминированного ключа, сгенерированного на основе seed-пароля (алгоритм Fernet).
"""

import base64
import hashlib
import os
import struct
from collections.abc import Callable
from pathlib import Path

from chutils.exceptions import OptionalDependencyError

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover
    # Оставляем заглушки для импорта, чтобы предотвратить AttributeError
    Fernet = None  # type: ignore
    InvalidToken = None  # type: ignore
    AESGCM = None  # type: ignore
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


def decrypt_portable(
        encrypted_data: str,
        seed: str,
        raise_on_error: bool = False
) -> str | None:
    """Дешифрует строку с использованием детерминированного ключа, полученного из seed.

    Args:
        encrypted_data: Зашифрованная строка в формате Base64.
        seed: Строка-пароль для генерации ключа.
        raise_on_error: Если True, выбрасывает ValueError при ошибке
            дешифрования (неверный ключ или поврежденный токен).

    Returns:
        Расшифрованная строка или None, если дешифрование завершилось ошибкой.

    Raises:
        OptionalDependencyError: Если библиотека cryptography не установлена.
        ValueError: Если raise_on_error равен True и произошла ошибка дешифрования.
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
    except (InvalidToken, Exception) as exc:
        if raise_on_error:
            raise ValueError(f"Не удалось расшифровать данные: неверный ключ или повреждённый токен ({exc})") from exc
        return None


STREAM_MAGIC = b"CHSTRM\x01"
DEFAULT_CHUNK_SIZE = 64 * 1024 * 1024


def _derive_aesgcm_key(seed: str, salt: bytes) -> bytes:
    """Генерирует 32-байтный AES-GCM ключ на основе seed и salt."""
    return hashlib.pbkdf2_hmac("sha256", seed.encode("utf-8"), salt, iterations=100000, dklen=32)


def _encrypt_stream_file(
    file_path: Path,
    seed: str,
    output_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """Шифрует файл в потоковом режиме с использованием AES-GCM и фиксированного объема RAM."""
    salt = os.urandom(16)
    key = _derive_aesgcm_key(seed, salt)
    aesgcm = AESGCM(key)

    total_size = file_path.stat().st_size
    processed_size = 0

    temp_out = output_path.with_suffix(output_path.suffix + ".tmp_enc")

    try:
        with open(file_path, "rb") as fin, open(temp_out, "wb") as fout:
            # Пишем Header: MAGIC (8B) + chunk_size (4B uint32) + salt (16B)
            fout.write(STREAM_MAGIC)
            fout.write(struct.pack(">I", chunk_size))
            fout.write(salt)

            if progress_callback:
                progress_callback(0, total_size)

            chunk_index = 0
            while True:
                chunk = fin.read(chunk_size)
                if not chunk:
                    break

                # Nonce: 12 B (8 B random + 4 B chunk_index)
                nonce = os.urandom(8) + struct.pack(">I", chunk_index)
                encrypted_chunk = aesgcm.encrypt(nonce, chunk, None)

                # Записываем nonce (12B) + len (4B) + encrypted_payload
                fout.write(nonce)
                fout.write(struct.pack(">I", len(encrypted_chunk)))
                fout.write(encrypted_chunk)

                processed_size += len(chunk)
                if progress_callback:
                    progress_callback(processed_size, total_size)

                chunk_index += 1

        if temp_out.exists():
            if output_path.exists() and temp_out != output_path:
                output_path.unlink()
            temp_out.replace(output_path)

        return output_path
    except Exception:
        if temp_out.exists():
            try:
                temp_out.unlink()
            except Exception:
                pass
        raise


def _decrypt_stream_file(
    file_path: Path,
    seed: str,
    output_path: Path,
    raise_on_error: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool:
    """Расшифровывает файл, зашифрованный в потоковом режиме."""
    temp_out = output_path.with_suffix(output_path.suffix + ".tmp_dec")
    total_size = file_path.stat().st_size
    processed_size = 0

    try:
        with open(file_path, "rb") as fin:
            magic = fin.read(len(STREAM_MAGIC))
            if magic != STREAM_MAGIC:
                raise ValueError("Неподдерживаемый формат потокового файла или поврежден заголовок")
            processed_size += len(magic)

            chunk_size_bytes = fin.read(4)
            if len(chunk_size_bytes) < 4:
                raise ValueError("Поврежден заголовок файла (размер чанка)")
            chunk_size = struct.unpack(">I", chunk_size_bytes)[0]
            processed_size += 4

            salt = fin.read(16)
            if len(salt) < 16:
                raise ValueError("Поврежден заголовок файла (salt)")
            processed_size += 16

            key = _derive_aesgcm_key(seed, salt)
            aesgcm = AESGCM(key)

            if progress_callback:
                progress_callback(processed_size, total_size)

            with open(temp_out, "wb") as fout:
                chunk_index = 0
                while True:
                    nonce = fin.read(12)
                    if not nonce:
                        break  # Конец файла
                    if len(nonce) < 12:
                        raise ValueError(f"Поврежден nonce чанка #{chunk_index}")

                    len_bytes = fin.read(4)
                    if len(len_bytes) < 4:
                        raise ValueError(f"Повреждена длина чанка #{chunk_index}")
                    payload_len = struct.unpack(">I", len_bytes)[0]

                    payload = fin.read(payload_len)
                    if len(payload) < payload_len:
                        raise ValueError(f"Поврежден payload чанка #{chunk_index}")

                    try:
                        decrypted_chunk = aesgcm.decrypt(nonce, payload, None)
                    except Exception as exc:
                        raise ValueError(
                            f"Сбой аутентификации чанка #{chunk_index}: неверный ключ или данные повреждены ({exc})"
                        ) from exc

                    fout.write(decrypted_chunk)
                    processed_size += 12 + 4 + payload_len
                    if progress_callback:
                        progress_callback(processed_size, total_size)

                    chunk_index += 1

        if temp_out.exists():
            if output_path.exists() and temp_out != output_path:
                output_path.unlink()
            temp_out.replace(output_path)

        return True
    except Exception as exc:
        if temp_out.exists():
            try:
                temp_out.unlink()
            except Exception:
                pass
        if raise_on_error:
            raise ValueError(f"Не удалось расшифровать потоковый файл: {exc}") from exc
        return False


def encrypt_file(
    file_path: str | Path,
    seed: str,
    output_path: str | Path | None = None,
    stream: bool = False,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """Шифрует содержимое файла и сохраняет результат.

    Args:
        file_path: Путь к исходному файлу.
        seed: Строка-пароль для генерации ключа.
        output_path: Путь для сохранения результата. Если не указан,
            исходный файл перезаписывается.
        stream: Если True, использовать потоковое чанковое шифрование (AES-GCM)
            с фиксированным потреблением памяти (для гигантских файлов).
        chunk_size: Размер чанка в байтах при потоковом шифровании (по умолчанию 64 МБ).
        progress_callback: Необязательная функция обратной связи (callback(processed, total))
            для отслеживания прогресса (например, для прогресс-бара).

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

    if stream:
        return _encrypt_stream_file(fp, seed, out_p, chunk_size=chunk_size, progress_callback=progress_callback)

    total_size = fp.stat().st_size
    if progress_callback:
        progress_callback(0, total_size)

    data_bytes = fp.read_bytes()
    key = _get_fernet_key(seed)
    f = Fernet(key)
    encrypted_bytes = f.encrypt(data_bytes)
    out_p.write_bytes(encrypted_bytes)  # chutils: ignore[ChutilsIntegrationRule]

    if progress_callback:
        progress_callback(total_size, total_size)

    return out_p


def decrypt_file(
    file_path: str | Path,
    seed: str,
    output_path: str | Path | None = None,
    raise_on_error: bool = False,
    stream: bool | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool:
    """Дешифрует содержимое файла и сохраняет результат.

    Args:
        file_path: Путь к зашифрованному файлу.
        seed: Строка-пароль для генерации ключа.
        output_path: Путь для сохранения результата. Если не указан,
            файл перезаписывается.
        raise_on_error: Если True, выбрасывает ValueError при ошибке
            дешифрования (неверный ключ или поврежденный файл).
        stream: Если True или None, автоопределяет и расшифровывает потоковый файл.
        progress_callback: Необязательная функция обратной связи (callback(processed, total))
            для отслеживания прогресса (например, для прогресс-бара).

    Returns:
        True, если дешифрование прошло успешно, иначе False.

    Raises:
        OptionalDependencyError: Если библиотека cryptography не установлена.
        ValueError: Если raise_on_error равен True и произошла ошибка дешифрования.
    """
    if not _HAS_CRYPTOGRAPHY:
        raise OptionalDependencyError(
            "Для использования модуля crypto установите библиотеку:\n"
            "pip install chutils[crypto]"
        )

    fp = Path(file_path)
    out_p = Path(output_path) if output_path is not None else fp

    # Автоматическое определение потокового формата по магическим байтам
    is_stream = stream
    if is_stream is None:
        try:
            with open(fp, "rb") as header_file:
                header = header_file.read(len(STREAM_MAGIC))
                is_stream = (header == STREAM_MAGIC)
        except Exception:
            is_stream = False

    if is_stream:
        return _decrypt_stream_file(fp, seed, out_p, raise_on_error=raise_on_error, progress_callback=progress_callback)

    total_size = fp.stat().st_size
    if progress_callback:
        progress_callback(0, total_size)

    try:
        encrypted_bytes = fp.read_bytes()
        key = _get_fernet_key(seed)
        f = Fernet(key)
        decrypted_bytes = f.decrypt(encrypted_bytes)
        out_p.write_bytes(decrypted_bytes)  # chutils: ignore[ChutilsIntegrationRule]
        if progress_callback:
            progress_callback(total_size, total_size)
        return True
    except (InvalidToken, Exception) as exc:
        if raise_on_error:
            raise ValueError(f"Не удалось расшифровать файл: неверный ключ или повреждённые данные ({exc})") from exc
        return False
