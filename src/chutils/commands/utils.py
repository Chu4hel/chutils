import importlib
from typing import Any


def _import_string(import_str: str) -> Any:
    """
    Импортирует объект по строковому пути (например, 'package.module.Class').
    
    Args:
        import_str: Строка импорта. Может содержать ':' или '.' как разделитель объекта.
        
    Returns:
        Импортированный объект или None при ошибке.
    """
    try:
        if ':' in import_str:
            module_name, obj_name = import_str.split(':', 1)
        else:
            module_name, obj_name = import_str.rsplit('.', 1)

        module = importlib.import_module(module_name)
        return getattr(module, obj_name)
    except (ImportError, AttributeError, ValueError):
        return None
