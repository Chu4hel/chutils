"""
Модуль для надежных операций с файловой системой.
Обеспечивает атомарную запись, безопасное создание директорий и работу с временными файлами.
"""

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Union, Any, ContextManager

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Гарантирует существование директории. Создает все родительские директории, если они не существуют.

    Args:
        path: Путь к директории (строка или pathlib.Path).

    Returns:
        Объект pathlib.Path.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write(
        file_path: Union[str, Path],
        data: Any,
        mode: str = 'w',
        encoding: str = 'utf-8',
        **kwargs: Any
) -> None:
    """
    Атомарная запись данных в файл.

    Данные сначала записываются во временный файл в той же директории,
    после чего выполняется атомарная замена целевого файла (os.replace).
    Это гарантирует, что файл не будет поврежден при сбое во время записи.

    Поддерживает автоматическую сериализацию для JSON и YAML на основе расширения файла.

    Args:
        file_path: Путь к целевому файлу.
        data: Данные для записи. Может быть строкой, байтами, словарем или списком.
        mode: Режим открытия файла ('w' или 'wb').
        encoding: Кодировка (только для текстового режима).
        **kwargs: Дополнительные аргументы для json.dump или yaml.dump.
    """
    target_path = Path(file_path)
    parent_dir = target_path.parent
    ensure_dir(parent_dir)

    suffix = target_path.suffix.lower()
    is_binary = 'b' in mode

    # Создаем временный файл в той же директории
    fd, temp_path_str = tempfile.mkstemp(dir=str(parent_dir), prefix=f".{target_path.name}.", suffix=".tmp")
    temp_path = Path(temp_path_str)

    try:
        if suffix == '.json' and isinstance(data, (dict, list)):
            with os.fdopen(fd, mode, encoding=None if is_binary else encoding) as f:
                json.dump(data, f, **kwargs)
        elif suffix in ('.yml', '.yaml') and isinstance(data, (dict, list)):
            if not YAML_AVAILABLE:
                raise ImportError("Пакет 'pyyaml' не установлен. Автоматическая сериализация YAML невозможна.")
            with os.fdopen(fd, mode, encoding=None if is_binary else encoding) as f:
                yaml.dump(data, f, **kwargs)
        else:
            with os.fdopen(fd, mode, encoding=None if is_binary else encoding) as f:
                f.write(data)

        # Атомарная замена
        os.replace(temp_path, target_path)
    except Exception:
        # В случае ошибки закрываем дескриптор (если он еще открыт) и удаляем временный файл
        if temp_path.exists():
            try:
                os.close(fd)
            except OSError:
                pass
            temp_path.unlink(missing_ok=True)
        raise


@contextmanager
def get_temp_file(suffix: str = '') -> ContextManager[Path]:
    """
    Контекстный менеджер для работы с временным файлом.
    Файл автоматически удаляется при выходе из блока with.

    Args:
        suffix: Суффикс (расширение) временного файла.

    Yields:
        Объект pathlib.Path к временному файлу.
    """
    # Создаем временный файл
    fd, temp_path_str = tempfile.mkstemp(suffix=suffix)
    temp_path = Path(temp_path_str)

    # Закрываем дескриптор сразу, так как пользователю нужен путь,
    # и он сам откроет его в нужном режиме.
    os.close(fd)

    try:
        yield temp_path
    finally:
        # Гарантированное удаление
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
