"""
Генератор шаблонов и схем конфигурации на основе Pydantic моделей.
"""

import json
from typing import Any, Type

try:
    from pydantic import BaseModel
    from pydantic.fields import FieldInfo

    PYDANTIC_AVAILABLE = True
except ImportError:
    class BaseModel:  # type: ignore
        """Заглушка для работы без Pydantic."""
        pass

    class FieldInfo:  # type: ignore
        """Заглушка для работы без Pydantic."""
        pass

    PYDANTIC_AVAILABLE = False


def _check_pydantic():
    if not PYDANTIC_AVAILABLE:
        raise ImportError(
            "Pydantic is required for configuration bootstrapping. "
            "Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'."
        )


def generate_yaml_template(model_class: Type[BaseModel], indent: int = 0) -> str:
    """
    Генерирует YAML шаблон на основе Pydantic модели с комментариями.
    """
    _check_pydantic()
    lines = []

    # Рекурсивный обход полей
    for field_name, field in model_class.model_fields.items():
        description = field.description
        default = field.default

        # Если значение по умолчанию - Pydantic модель (вложенность)
        # Или тип поля - подкласс BaseModel
        field_type = field.annotation

        # Обработка вложенных моделей
        is_nested = False
        nested_model = None

        # Проверяем, является ли тип наследником BaseModel
        try:
            if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                is_nested = True
                nested_model = field_type
        except TypeError:
            pass

        # Добавляем комментарий, если есть описание
        if description:
            lines.append(f"{'  ' * indent}# {description}")

        if is_nested and nested_model:
            lines.append(f"{'  ' * indent}{field_name}:")
            lines.append(generate_yaml_template(nested_model, indent + 1))
        else:
            # Форматируем значение по умолчанию
            val_str = "null"
            if default is not None and default is not ...:  # ... это Pydantic Missing
                if isinstance(default, str):
                    val_str = f'"{default}"'
                elif isinstance(default, bool):
                    val_str = str(default).lower()
                else:
                    val_str = str(default)
            elif field.is_required():
                val_str = "# ОБЯЗАТЕЛЬНОЕ ПОЛЕ"

            lines.append(f"{'  ' * indent}{field_name}: {val_str}")

    return "\n".join(lines)


def generate_env_template(model_class: Type[BaseModel], prefix: str = "CH") -> str:
    """
    Генерирует .env шаблон (плоский формат).
    """
    _check_pydantic()
    lines = []

    def _walk(model: Type[BaseModel], current_prefix: str):
        for field_name, field in model.model_fields.items():
            env_name = f"{current_prefix}_{field_name.upper()}"
            description = field.description
            default = field.default

            field_type = field.annotation
            is_nested = False
            nested_model = None
            try:
                if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                    is_nested = True
                    nested_model = field_type
            except TypeError:
                pass

            if is_nested and nested_model:
                _walk(nested_model, env_name)
            else:
                if description:
                    lines.append(f"# {description}")

                val_str = ""
                if default is not None and default is not ...:
                    val_str = str(default)
                elif field.is_required():
                    val_str = "REPLACE_ME"

                lines.append(f"{env_name}={val_str}")
                lines.append("")  # Пустая строка для читаемости

    _walk(model_class, prefix)
    return "\n".join(lines).strip()


def generate_json_schema(model_class: Type[BaseModel]) -> str:
    """
    Генерирует JSON схему на основе Pydantic модели.
    """
    _check_pydantic()
    schema = model_class.model_json_schema()
    return json.dumps(schema, indent=4, ensure_ascii=False)
