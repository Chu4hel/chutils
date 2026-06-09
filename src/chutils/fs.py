"""
Модуль для надежных операций с файловой системой.
Обеспечивает атомарную запись, безопасное создание директорий и работу с временными файлами.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Union, Any, Optional, Generator, TYPE_CHECKING

from chutils.exceptions import OptionalDependencyError, PathTraversalError

if TYPE_CHECKING:
    import yaml

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def resolve_safe_path(path: Union[str, Path], base_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Безопасно разрешает путь относительно базовой директории.
    Проверяет попытки выхода за пределы базовой директории (Path Traversal).

    Args:
        path: Путь для разрешения.
        base_dir: Базовая директория. Если не указана, используется корень проекта из конфига.

    Returns:
        Разрешенный абсолютный путь (pathlib.Path).

    Raises:
        PathTraversalError: Если обнаружена попытка выхода за пределы base_dir.
    """
    if base_dir is None:
        try:
            from chutils.config import get_base_dir
            base_dir = get_base_dir()
        except (ImportError, AttributeError):
            base_dir = Path.cwd()

    if not base_dir:
        base_dir = Path.cwd()

    p = Path(path)
    base = Path(base_dir).resolve()

    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (base / p).resolve()

    # Сравниваем разрешенные пути
    if not str(resolved).startswith(str(base)):
        raise PathTraversalError(
            f"Обнаружена попытка выхода за пределы разрешенной директории: {path}",
            attempted_path=path,
            base_path=base_dir
        )

    return resolved


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

    Raises:
        OptionalDependencyError: Если выполняется запись в YAML, но пакет `pyyaml` не установлен.
        OSError: При ошибках ввода-вывода.
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
                raise OptionalDependencyError(
                    "Пакет 'pyyaml' не установлен. Автоматическая сериализация YAML невозможна.",
                    dependency="pyyaml"
                )
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
def get_temp_file(suffix: str = '') -> Generator[Path, None, None]:
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
