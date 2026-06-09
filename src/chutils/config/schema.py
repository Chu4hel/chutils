"""
Утилиты для генерации и экспорта JSON Schema на основе Pydantic моделей.
"""

import importlib
import json
import typing as t
from pathlib import Path
from typing import Optional, Type, Union

from ..env import PYDANTIC_AVAILABLE
from ..exceptions import OptionalDependencyError, ConfigParseError

if t.TYPE_CHECKING:
    from pydantic import BaseModel
else:
    try:
        from pydantic import BaseModel
    except ImportError:
        class BaseModel:  # type: ignore[no-redef]
            """Заглушка для работы без Pydantic."""
            pass


def _check_pydantic() -> None:
    """Проверяет наличие Pydantic."""
    if not PYDANTIC_AVAILABLE:
        raise OptionalDependencyError(
            "Pydantic необходим для генерации JSON Schema.",
            dependency="pydantic",
            hint="Установите его: pip install chutils[pydantic] или poetry add pydantic"
        )


def import_model_class(model_path: str) -> Type[BaseModel]:
    """
    Импортирует класс Pydantic модели по строковому пути.

    Args:
        model_path: Путь к модели в формате 'module.path:ClassName'.

    Returns:
        Класс модели (BaseModel).

    Raises:
        ConfigParseError: Если формат пути некорректен или класс не найден.
        OptionalDependencyError: Если Pydantic не установлен.
    """
    _check_pydantic()

    if ":" not in model_path:
        raise ConfigParseError(
            f"Некорректный формат пути к модели: '{model_path}'",
            hint="Ожидается 'module.path:ClassName'. Пример: 'myapp.config:Settings'"
        )

    module_name, class_name = model_path.split(":", 1)

    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise ConfigParseError(
            f"Не удалось импортировать модуль '{module_name}': {e}",
            hint=f"Убедитесь, что модуль '{module_name}' существует и доступен для импорта."
        )

    model_class = getattr(module, class_name, None)
    if model_class is None:
        raise ConfigParseError(
            f"Класс '{class_name}' не найден в модуле '{module_name}'.",
            hint="Проверьте правильность написания имени класса."
        )

    if not isinstance(model_class, type) or not issubclass(model_class, BaseModel):
        raise ConfigParseError(
            f"Объект '{model_path}' не является подклассом pydantic.BaseModel.",
            hint="Ваша модель должна наследоваться от pydantic.BaseModel."
        )

    return model_class


def export_schema(
        model: Union[Type[BaseModel], str],
        output_path: Optional[Union[str, Path]] = None,
        indent: int = 4
) -> str:
    """
    Генерирует JSON Schema для Pydantic модели и опционально сохраняет в файл.

    Args:
        model: Класс модели или строковый путь к нему ('module:Class').
        output_path: Путь к файлу для сохранения схемы.
        indent: Отступ в результирующем JSON.

    Returns:
        Строка с JSON Schema.
    """
    _check_pydantic()

    if isinstance(model, str):
        model_class = import_model_class(model)
    else:
        model_class = model

    # Генерируем схему через Pydantic
    schema = model_class.model_json_schema()

    # Добавляем стандартный заголовок $schema, если его нет (Pydantic его не добавляет по умолчанию)
    if "$schema" not in schema:
        # Используем актуальный драфт (2020-12) или 7, наиболее совместимые с IDE
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **schema
        }

    schema_str = json.dumps(schema, indent=indent, ensure_ascii=False)

    if output_path:
        path = Path(output_path)
        # Создаем директории, если их нет
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(schema_str, encoding="utf-8")

    return schema_str
