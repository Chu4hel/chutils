from __future__ import annotations

import keyword
import re
from pathlib import Path

from chutils.exceptions import CommandError

# Регулярное выражение для валидации имени модуля (PEP 8)
MODULE_NAME_REGEX = re.compile(r"^[a-z_][a-z0-9_]*$")


def to_camel_case(s: str) -> str:
    """Преобразует snake_case строку в CamelCase.

    Args:
        s: Входная строка в стиле snake_case.

    Returns:
        Строка, преобразованная в CamelCase.
    """
    return "".join(word.capitalize() for word in s.split("_"))


# --- Шаблоны кода для генератора ---

TEMPLATES: dict[str, str] = {
    "__init__.py": """from __future__ import annotations

from .container import Container as Container
from .domain.entities import {entity_name} as {entity_name}
from .domain.value_objects import {value_object_name} as {value_object_name}

__all__ = [
    "Container",
    "{entity_name}",
    "{value_object_name}",
]
""",
    "container.py": """from __future__ import annotations

from .application.use_cases import Create{entity_name}UseCase, Get{entity_name}UseCase
from .infrastructure.db_adapters import DatabaseAdapter
from .infrastructure.repositories import Memory{entity_name}Repository
from .presentation.api import APIController
from .presentation.cli import CLIController


class Container:
    \"\"\"Декларативный контейнер зависимостей для модуля {module_name}.\"\"\"

    def __init__(self) -> None:
        # Инфраструктура
        self.db_adapter = DatabaseAdapter()
        self.repository = Memory{entity_name}Repository(self.db_adapter)

        # Прикладной слой (Use Cases)
        self.create_use_case = Create{entity_name}UseCase(self.repository)
        self.get_use_case = Get{entity_name}UseCase(self.repository)

        # Слой представления
        self.cli_controller = CLIController(
            create_use_case=self.create_use_case,
            get_use_case=self.get_use_case,
        )
        self.api_controller = APIController(
            create_use_case=self.create_use_case,
            get_use_case=self.get_use_case,
        )
""",
    "domain/__init__.py": """from __future__ import annotations

from .entities import Entity as Entity
from .entities import {entity_name} as {entity_name}
from .repositories import {entity_name}Repository as {entity_name}Repository
from .value_objects import {value_object_name} as {value_object_name}
from .value_objects import ValueObject as ValueObject

__all__ = [
    "Entity",
    "{entity_name}",
    "{value_object_name}",
    "{entity_name}Repository",
    "ValueObject",
]
""",
    "domain/entities.py": """from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Entity:
    \"\"\"Базовый класс для всех доменных сущностей (Entities).\"\"\"
    id: str


@dataclass
class {entity_name}(Entity):
    \"\"\"Пример доменной сущности.\"\"\"
    name: str
    is_active: bool
""",
    "domain/value_objects.py": """from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    \"\"\"Базовый класс для Value Objects (объектов-значений).\"\"\"


@dataclass(frozen=True)
class {value_object_name}(ValueObject):
    \"\"\"Пример Value Object.\"\"\"
    value: str
""",
    "domain/repositories.py": """from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .entities import {entity_name}


class {entity_name}Repository(ABC):
    \"\"\"Абстрактный интерфейс репозитория для {entity_name}.\"\"\"

    @abstractmethod
    def get_by_id(self, entity_id: str) -> {entity_name} | None:
        \"\"\"Получить сущность по идентификатору.\"\"\"

    @abstractmethod
    def save(self, entity: {entity_name}) -> None:
        \"\"\"Сохранить или обновить сущность.\"\"\"

    @abstractmethod
    def list_all(self) -> Sequence[{entity_name}]:
        \"\"\"Получить список всех сущностей.\"\"\"
""",
    "application/__init__.py": """from __future__ import annotations

from .use_cases import (
    Create{entity_name}UseCase as Create{entity_name}UseCase,
)
from .use_cases import (
    Get{entity_name}UseCase as Get{entity_name}UseCase,
)
from .use_cases import (
    UseCase as UseCase,
)

__all__ = [
    "Create{entity_name}UseCase",
    "Get{entity_name}UseCase",
    "UseCase",
]
""",
    "application/use_cases.py": """from __future__ import annotations

from ..domain.entities import {entity_name}
from ..domain.repositories import {entity_name}Repository


class UseCase:
    \"\"\"Базовый класс сценария использования.\"\"\"


class Get{entity_name}UseCase(UseCase):
    \"\"\"Сценарий получения сущности по ID.\"\"\"

    def __init__(self, repository: {entity_name}Repository) -> None:
        self.repository = repository

    def execute(self, entity_id: str) -> {entity_name} | None:
        return self.repository.get_by_id(entity_id)


class Create{entity_name}UseCase(UseCase):
    \"\"\"Сценарий создания новой сущности.\"\"\"

    def __init__(self, repository: {entity_name}Repository) -> None:
        self.repository = repository

    def execute(self, entity_id: str, name: str) -> {entity_name}:
        entity = {entity_name}(id=entity_id, name=name, is_active=True)
        self.repository.save(entity)
        return entity
""",
    "infrastructure/__init__.py": """from __future__ import annotations

from .db_adapters import DatabaseAdapter as DatabaseAdapter
from .repositories import Memory{entity_name}Repository as Memory{entity_name}Repository

__all__ = [
    "DatabaseAdapter",
    "Memory{entity_name}Repository",
]
""",
    "infrastructure/db_adapters.py": """from __future__ import annotations


class DatabaseAdapter:
    \"\"\"Адаптер для работы с базой данных (заглушка in-memory).\"\"\"

    def __init__(self) -> None:
        self._storage: dict[str, dict[str, str | bool]] = {{}}

    def fetch(self, key: str) -> dict[str, str | bool] | None:
        return self._storage.get(key)

    def store(self, key: str, data: dict[str, str | bool]) -> None:
        self._storage[key] = data

    def fetch_all(self) -> list[dict[str, str | bool]]:
        return list(self._storage.values())
""",
    "infrastructure/repositories.py": """from __future__ import annotations

from collections.abc import Sequence

from ..domain.entities import {entity_name}
from ..domain.repositories import {entity_name}Repository
from .db_adapters import DatabaseAdapter


class Memory{entity_name}Repository({entity_name}Repository):
    \"\"\"Конкретная реализация репозитория {entity_name} на базе in-memory БД.\"\"\"

    def __init__(self, db_adapter: DatabaseAdapter) -> None:
        self.db_adapter = db_adapter

    def get_by_id(self, entity_id: str) -> {entity_name} | None:
        data = self.db_adapter.fetch(entity_id)
        if not data:
            return None
        return {entity_name}(
            id=str(data["id"]),
            name=str(data["name"]),
            is_active=bool(data["is_active"]),
        )

    def save(self, entity: {entity_name}) -> None:
        self.db_adapter.store(
            entity.id,
            {{
                "id": entity.id,
                "name": entity.name,
                "is_active": entity.is_active,
            }},
        )

    def list_all(self) -> Sequence[{entity_name}]:
        results = []
        for data in self.db_adapter.fetch_all():
            results.append(
                {entity_name}(
                    id=str(data["id"]),
                    name=str(data["name"]),
                    is_active=bool(data["is_active"]),
                )
            )
        return results
""",
    "presentation/__init__.py": """from __future__ import annotations

from .api import APIController as APIController
from .cli import CLIController as CLIController

__all__ = [
    "APIController",
    "CLIController",
]
""",
    "presentation/cli.py": """from __future__ import annotations

from ..application.use_cases import Create{entity_name}UseCase, Get{entity_name}UseCase


class CLIController:
    \"\"\"CLI контроллер для взаимодействия с пользователем.\"\"\"

    def __init__(
        self,
        create_use_case: Create{entity_name}UseCase,
        get_use_case: Get{entity_name}UseCase,
    ) -> None:
        self.create_use_case = create_use_case
        self.get_use_case = get_use_case

    def create(self, entity_id: str, name: str) -> str:
        entity = self.create_use_case.execute(entity_id, name)
        return f"Сущность {{entity.name}} (ID: {{entity.id}}) успешно создана."

    def get(self, entity_id: str) -> str:
        entity = self.get_use_case.execute(entity_id)
        if not entity:
            return f"Сущность с ID {{entity_id}} не найдена."
        return f"Найдена сущность: {{entity.name}} (Активна: {{entity.is_active}})"
""",
    "presentation/api.py": """from __future__ import annotations

from ..application.use_cases import Create{entity_name}UseCase, Get{entity_name}UseCase


class APIController:
    \"\"\"API контроллер для веб-запросов (имитация).\"\"\"

    def __init__(
        self,
        create_use_case: Create{entity_name}UseCase,
        get_use_case: Get{entity_name}UseCase,
    ) -> None:
        self.create_use_case = create_use_case
        self.get_use_case = get_use_case

    def handle_get_entity(self, entity_id: str) -> dict[str, str | bool]:
        entity = self.get_use_case.execute(entity_id)
        if not entity:
            return {{"error": "Not Found"}}
        return {{
            "id": entity.id,
            "name": entity.name,
            "is_active": entity.is_active,
        }}

    def handle_create_entity(self, entity_id: str, name: str) -> dict[str, str | bool]:
        entity = self.create_use_case.execute(entity_id, name)
        return {{
            "id": entity.id,
            "name": entity.name,
            "is_active": entity.is_active,
        }}
""",
}


class Scaffolder:
    """Генератор слоев Чистой Архитектуры для нового модуля."""

    def __init__(
            self,
            module_name: str,
            output_dir: str | None = None,
            force: bool = False,
    ) -> None:
        """Инициализирует Scaffolder.

        Args:
            module_name: Имя генерируемого модуля.
            output_dir: Путь, куда будет сгенерирован модуль.
            force: Флаг принудительной генерации (перезаписи).
        """
        self.module_name = module_name.strip()
        self.force = force

        # Определение пути вывода
        if output_dir:
            self.output_path = Path(output_dir).resolve()
        else:
            self.output_path = Path(".").resolve() / self.module_name

    def validate(self) -> None:
        """Проверяет имя модуля и доступность каталога."""
        if not self.module_name:
            raise CommandError("Имя модуля не может быть пустым.")

        if not MODULE_NAME_REGEX.match(self.module_name):
            raise CommandError(
                f"Некорректное имя модуля '{self.module_name}'. "
                "Имя должно состоять из строчных латинских букв, цифр и символов подчеркивания, "
                "и не должно начинаться с цифры (PEP 8)."
            )

        if keyword.iskeyword(self.module_name):
            raise CommandError(
                f"Имя модуля '{self.module_name}' является зарезервированным ключевым словом Python."
            )

        # Проверка существования директории
        if self.output_path.exists() and not self.force:
            # Проверяем, пустая ли это директория
            is_empty = True
            if self.output_path.is_dir():
                try:
                    is_empty = not any(self.output_path.iterdir())
                except OSError:
                    is_empty = False
            else:
                is_empty = False

            if not is_empty:
                raise CommandError(
                    f"Целевая директория '{self.output_path}' уже существует и не пуста. "
                    "Используйте флаг --force для перезаписи."
                )

    def scaffold(self) -> None:
        """Запускает процесс генерации структуры."""
        self.validate()

        # Подготовка имен для плейсхолдеров
        camel_module = to_camel_case(self.module_name)
        entity_name = camel_module
        value_object_name = f"{camel_module}Config"

        # Запись файлов
        for rel_path, template_str in TEMPLATES.items():
            file_path = self.output_path / rel_path

            # Создаем родительские директории, если их нет
            from chutils.fs import ensure_dir, atomic_write  # chutils: ignore[ChutilsIntegrationRule]
            ensure_dir(file_path.parent)

            # Интерполяция шаблона
            content = template_str.format(
                module_name=self.module_name,
                entity_name=entity_name,
                value_object_name=value_object_name,
            )

            # Запись с перезаписью (если force=True, это затрет существующий файл) chutils: ignore[ChutilsIntegrationRule]
            atomic_write(file_path, content)
