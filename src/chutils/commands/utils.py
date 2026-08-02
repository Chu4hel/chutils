import importlib
import sys
from pathlib import Path
from typing import Any


def ensure_project_paths_in_sys_path() -> None:
    """Гарантирует, что текущая рабочая директория и папка 'src' добавлены в sys.path."""
    cwd = Path.cwd().resolve()
    cwd_str = str(cwd)
    src_str = str(cwd / "src")

    if cwd_str not in sys.path:
        sys.path.insert(0, cwd_str)
    if (cwd / "src").is_dir() and src_str not in sys.path:
        sys.path.insert(0, src_str)


def _import_string(import_str: str) -> Any:
    """
    Импортирует объект по строковому пути (например, 'package.module.Class').
    Автоматически учитывает структуру проекта (включая src-layout).

    Args:
        import_str: Строка импорта. Может содержать ':' или '.' как разделитель объекта.

    Returns:
        Импортированный объект или None при ошибке.
    """
    ensure_project_paths_in_sys_path()

    try:
        if ':' in import_str:
            module_name, obj_name = import_str.split(':', 1)
        else:
            module_name, obj_name = import_str.rsplit('.', 1)

        module = importlib.import_module(module_name)
        return getattr(module, obj_name)
    except (ImportError, AttributeError, ValueError):
        return None
