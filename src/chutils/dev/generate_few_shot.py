"""
Автогенерация Few-shot банков примеров для целевых проектов.

Команда ``chutils dev generate-few-shot`` анализирует архитектуру
целевого проекта и создаёт банк few-shot примеров ``docs/ai_examples/``
для обучения LLM-агентов стандартам написания кода в данном проекте.
"""
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


# ---------------------------------------------------------------------------
# Модели
# ---------------------------------------------------------------------------

@dataclass
class DetectedEntities:
    """Результат анализа архитектуры целевого проекта.

    Attrs:
        use_cases: Имена найденных классов Use Case / Interactor.
        repositories: Имена найденных классов репозиториев.
        loggers: Имена переменных / вызовов логгеров.
        errors: Имена найденных пользовательских исключений.
        di_files: Имена файлов с DI-контейнерами.
        categories: Множество активных категорий.
    """

    use_cases: list[str] = field(default_factory=list)
    repositories: list[str] = field(default_factory=list)
    loggers: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    di_files: list[str] = field(default_factory=list)

    @property
    def categories(self) -> set[str]:
        """Возвращает набор активных категорий."""
        cats: set[str] = set()
        if self.use_cases:
            cats.add("use_cases")
        if self.repositories:
            cats.add("repositories")
        if self.loggers:
            cats.add("logging")
        if self.errors:
            cats.add("errors")
        if self.di_files:
            cats.add("di")
        return cats


@dataclass
class GenerationResult:
    """Результат генерации банка примеров.

    Attrs:
        created_categories: Список созданных (новых) категорий.
        skipped_categories: Список пропущенных категорий (уже существовали).
        manifest_updated: Был ли обновлён/создан GEMINI.md.
        output_dir: Путь к созданному банку примеров.
    """

    created_categories: list[str] = field(default_factory=list)
    skipped_categories: list[str] = field(default_factory=list)
    manifest_updated: bool = False
    output_dir: Path | None = None


# ---------------------------------------------------------------------------
# Детектор архитектурных абстракций
# ---------------------------------------------------------------------------

class ArchitectureDetector:
    """Анализирует AST целевого проекта для выявления архитектурных абстракций.

    Проходит по всем ``.py``-файлам проекта и собирает:
    - Имена Use Case / Interactor классов
    - Имена репозиториев (абстрактные классы для работы с БД)
    - Имена переменных / экземпляры логгеров
    - Имена пользовательских исключений
    - Наличие файлов DI-контейнеров
    """

    # Ключевые слова для определения архитектурных абстракций
    _USE_CASE_KEYWORDS: frozenset[str] = frozenset(
        {"UseCase", "Interactor", "use_case", "interactor"}
    )
    _REPO_KEYWORDS: frozenset[str] = frozenset(
        {"Repository", "Repo", "AbstractRepository", "BaseRepository"}
    )
    _DI_FILE_NAMES: frozenset[str] = frozenset(
        {"container.py", "di.py", "dependencies.py", "providers.py"}
    )
    _DI_IMPORT_KEYWORDS: frozenset[str] = frozenset(
        {"dependency_injector", "punq", "lagom", "dishka", "inject"}
    )
    _LOGGING_CALLS: frozenset[str] = frozenset(
        {"getLogger", "setup_logger", "get_logger", "logging"}
    )
    _EXCEPTION_BASE_NAMES: frozenset[str] = frozenset(
        {"Exception", "BaseException", "Error", "RuntimeError", "ValueError"}
    )

    def __init__(self, project_root: Path) -> None:
        self._root = project_root

    def detect(self) -> DetectedEntities:
        """Запускает анализ и возвращает найденные сущности.

        Returns:
            DetectedEntities со всеми найденными архитектурными абстракциями.
        """
        entities = DetectedEntities()
        seen_use_cases: set[str] = set()
        seen_repos: set[str] = set()
        seen_loggers: set[str] = set()
        seen_errors: set[str] = set()

        for py_file in self._iter_python_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            # DI — по имени файла
            if py_file.name in self._DI_FILE_NAMES:
                if py_file.stem not in entities.di_files:
                    entities.di_files.append(py_file.stem)

            # DI — по импортам DI-библиотек
            if not entities.di_files:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        module_name = ""
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                module_name = alias.name.split(".")[0]
                                if module_name in self._DI_IMPORT_KEYWORDS:
                                    entities.di_files.append(py_file.stem)
                                    break
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            module_name = node.module.split(".")[0]
                            if module_name in self._DI_IMPORT_KEYWORDS:
                                entities.di_files.append(py_file.stem)
                        if entities.di_files:
                            break

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name

                    # Use Cases
                    is_use_case = any(kw in class_name for kw in self._USE_CASE_KEYWORDS)
                    if not is_use_case:
                        for base in node.bases:
                            base_str = self._base_to_str(base)
                            if any(kw in base_str for kw in self._USE_CASE_KEYWORDS):
                                is_use_case = True
                                break
                    if is_use_case and class_name not in seen_use_cases:
                        seen_use_cases.add(class_name)
                        entities.use_cases.append(class_name)

                    # Repositories
                    is_repo = any(kw in class_name for kw in self._REPO_KEYWORDS)
                    if not is_repo:
                        for base in node.bases:
                            base_str = self._base_to_str(base)
                            if any(kw in base_str for kw in self._REPO_KEYWORDS):
                                is_repo = True
                                break
                        # Также проверяем декораторы (абстрактные классы)
                        is_abstract = any(
                            self._decorator_to_str(d) in {"abstractmethod", "ABC"}
                            for d in node.decorator_list
                        )
                        if is_abstract and "Repository" in class_name:
                            is_repo = True
                    if is_repo and class_name not in seen_repos:
                        seen_repos.add(class_name)
                        entities.repositories.append(class_name)

                    # Пользовательские исключения
                    for base in node.bases:
                        base_str = self._base_to_str(base)
                        if any(exc in base_str for exc in self._EXCEPTION_BASE_NAMES):
                            if class_name not in seen_errors:
                                seen_errors.add(class_name)
                                entities.errors.append(class_name)
                            break

                # Логгеры — по вызовам функций и присваиваниям
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if isinstance(node.value, ast.Call):
                                func_name = self._call_func_name(node.value)
                                if any(kw in func_name for kw in self._LOGGING_CALLS):
                                    var_name = target.id
                                    if var_name not in seen_loggers:
                                        seen_loggers.add(var_name)
                                        entities.loggers.append(var_name)

        return entities

    def _iter_python_files(self) -> list[Path]:
        """Возвращает список Python-файлов проекта (без скрытых папок и __pycache__).

        Returns:
            Список путей к ``.py``-файлам.
        """
        result: list[Path] = []
        skip_dirs = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".mypy_cache"}
        for py_file in self._root.rglob("*.py"):
            if any(part in skip_dirs or part.startswith(".") for part in py_file.parts):
                continue
            result.append(py_file)
        return result

    @staticmethod
    def _base_to_str(base: ast.expr) -> str:
        """Преобразует узел базового класса в строку.

        Args:
            base: AST-узел базового класса.

        Returns:
            Строковое представление базового класса.
        """
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            parts: list[str] = []
            curr: ast.expr = base
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
            return ".".join(reversed(parts))
        return ""

    @staticmethod
    def _decorator_to_str(dec: ast.expr) -> str:
        """Преобразует узел декоратора в строку.

        Args:
            dec: AST-узел декоратора.

        Returns:
            Строковое представление декоратора.
        """
        if isinstance(dec, ast.Name):
            return dec.id
        if isinstance(dec, ast.Attribute):
            return dec.attr
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
            return dec.func.id
        return ""

    @staticmethod
    def _call_func_name(call: ast.Call) -> str:
        """Извлекает имя функции из вызова.

        Args:
            call: AST-узел вызова функции.

        Returns:
            Имя вызываемой функции.
        """
        if isinstance(call.func, ast.Name):
            return call.func.id
        if isinstance(call.func, ast.Attribute):
            return call.func.attr
        return ""


# ---------------------------------------------------------------------------
# Генератор шаблонов
# ---------------------------------------------------------------------------

class TemplateRenderer:
    """Рендерит параметризованные шаблоны Good/Bad паттернов и README для каждой категории.

    Args:
        entities: Найденные архитектурные сущности.
    """

    def __init__(self, entities: DetectedEntities) -> None:
        self._entities = entities

    def render_good_pattern(self, category: str) -> str:
        """Генерирует код идеального паттерна для категории.

        Args:
            category: Название категории (use_cases, repositories, logging, errors, di).

        Returns:
            Строка с кодом Python.
        """
        renderers = {
            "use_cases": self._good_use_cases,
            "repositories": self._good_repositories,
            "logging": self._good_logging,
            "errors": self._good_errors,
            "di": self._good_di,
        }
        renderer = renderers.get(category)
        return renderer() if renderer else ""

    def render_bad_pattern(self, category: str) -> str:
        """Генерирует код антипаттерна для категории.

        Args:
            category: Название категории.

        Returns:
            Строка с кодом Python.
        """
        renderers = {
            "use_cases": self._bad_use_cases,
            "repositories": self._bad_repositories,
            "logging": self._bad_logging,
            "errors": self._bad_errors,
            "di": self._bad_di,
        }
        renderer = renderers.get(category)
        return renderer() if renderer else ""

    def render_readme(self, category: str) -> str:
        """Генерирует README.md с руководством для LLM по данной категории.

        Args:
            category: Название категории.

        Returns:
            Строка с Markdown-контентом.
        """
        readmes = {
            "use_cases": self._readme_use_cases,
            "repositories": self._readme_repositories,
            "logging": self._readme_logging,
            "errors": self._readme_errors,
            "di": self._readme_di,
        }
        renderer = readmes.get(category)
        return renderer() if renderer else f"# {category}\n\nNo description available.\n"

    # ------------------------------------------------------------------
    # Use Cases
    # ------------------------------------------------------------------

    def _good_use_cases(self) -> str:
        name = self._entities.use_cases[0] if self._entities.use_cases else "CreateOrderUseCase"
        return textwrap.dedent(f"""\
            \"\"\"Good pattern: Use Case с явной входной моделью и типизацией.\"\"\"
            from __future__ import annotations

            from dataclasses import dataclass


            @dataclass(frozen=True)
            class {name}Input:
                \"\"\"Входные данные для {name}.\"\"\"

                user_id: int
                payload: str


            @dataclass(frozen=True)
            class {name}Output:
                \"\"\"Результат выполнения {name}.\"\"\"

                result_id: int
                status: str


            class {name}:
                \"\"\"Реализует бизнес-сценарий: создаёт запись.

                Зависимости инжектируются через конструктор (DIP).
                \"\"\"

                def __init__(self, repository: object) -> None:
                    self._repo = repository

                def execute(self, input_data: {name}Input) -> {name}Output:
                    \"\"\"Выполняет сценарий.

                    Args:
                        input_data: Параметры входных данных.

                    Returns:
                        Результат выполнения сценария.

                    Raises:
                        ValueError: Если данные некорректны.
                    \"\"\"
                    if not input_data.payload:
                        raise ValueError("payload не может быть пустым")
                    # ... бизнес-логика ...
                    return {name}Output(result_id=1, status="created")
            """)

    def _bad_use_cases(self) -> str:
        name = self._entities.use_cases[0] if self._entities.use_cases else "CreateOrderUseCase"
        bad_name = name.replace("UseCase", "").replace("Interactor", "") or "CreateOrder"
        return textwrap.dedent(f"""\
            \"\"\"Bad pattern: Use Case нарушает SRP и DIP.\"\"\"
            import sqlite3  # noqa: F401  — прямой доступ к инфраструктуре


            class {bad_name}:
                # Антипаттерн: жёсткая связь с БД, нет типов, нет Input/Output
                def do(self, uid, data):
                    conn = sqlite3.connect("prod.db")   # Прямое подключение к БД — нарушение DIP
                    conn.execute(f"INSERT INTO t VALUES ({{uid}}, {{data}})")
                    conn.commit()
                    # Нет обработки ошибок, нет явного возврата
            """)

    def _readme_use_cases(self) -> str:
        names = ", ".join(self._entities.use_cases[:3]) if self._entities.use_cases else "CreateOrderUseCase"
        return textwrap.dedent(f"""\
            # Use Cases / Interactors

            В этом проекте обнаружены следующие Use Cases: **{names}**.

            ## Правила для ИИ-агентов

            1. **Один Use Case — одна ответственность.** Каждый класс реализует ровно один бизнес-сценарий.
            2. **Явные Input/Output модели.** Используй `@dataclass(frozen=True)` для входных и выходных данных.
            3. **Инверсия зависимостей (DIP).** Use Case зависит только от абстракций (ABC / Protocol), никогда от конкретных реализаций.
            4. **Не обращайся к БД напрямую.** Все операции с данными — через репозиторий.
            5. **Полная типизация.** Аргументы и возвращаемый тип метода `execute` обязательно аннотированы.

            ## Признаки хорошего паттерна

            - Класс содержит единственный метод `execute(input_data: ...)`.
            - Конструктор принимает только абстрактные зависимости.
            - `Input` и `Output` — иммутабельные dataclass.
            """)

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def _good_repositories(self) -> str:
        name = self._entities.repositories[0] if self._entities.repositories else "UserRepository"
        return textwrap.dedent(f"""\
            \"\"\"Good pattern: Абстрактный репозиторий + конкретная реализация.\"\"\"
            from __future__ import annotations

            from abc import ABC, abstractmethod
            from dataclasses import dataclass


            @dataclass(frozen=True)
            class User:
                id: int
                name: str


            class Abstract{name}(ABC):
                \"\"\"Интерфейс репозитория. Зависит только от доменных объектов.\"\"\"

                @abstractmethod
                def get_by_id(self, user_id: int) -> User | None:
                    \"\"\"Возвращает пользователя по идентификатору или None.

                    Args:
                        user_id: Идентификатор пользователя.

                    Returns:
                        Объект User или None, если не найден.
                    \"\"\"

                @abstractmethod
                def save(self, user: User) -> None:
                    \"\"\"Сохраняет пользователя.

                    Args:
                        user: Объект пользователя для сохранения.
                    \"\"\"


            class InMemory{name}(Abstract{name}):
                \"\"\"Реализация репозитория в памяти (для тестов).\"\"\"

                def __init__(self) -> None:
                    self._storage: dict[int, User] = {{}}

                def get_by_id(self, user_id: int) -> User | None:
                    return self._storage.get(user_id)

                def save(self, user: User) -> None:
                    self._storage[user.id] = user
            """)

    def _bad_repositories(self) -> str:
        name = self._entities.repositories[0] if self._entities.repositories else "UserRepository"
        return textwrap.dedent(f"""\
            \"\"\"Bad pattern: репозиторий нарушает абстракцию и утекает БД в домен.\"\"\"
            import sqlite3


            class {name}:
                # Антипаттерн: нет абстракции, прямой SQL, нет типов
                def get(self, id):
                    con = sqlite3.connect("./db.sqlite")
                    cur = con.cursor()
                    # SQL прямо в методе, нет типов, нет обработки ошибок
                    row = cur.execute(f"SELECT * FROM users WHERE id={{id}}").fetchone()
                    return row  # Возвращает сырой tuple, а не доменный объект
            """)

    def _readme_repositories(self) -> str:
        names = ", ".join(self._entities.repositories[:3]) if self._entities.repositories else "UserRepository"
        return textwrap.dedent(f"""\
            # Repositories (Репозитории)

            В проекте обнаружены репозитории: **{names}**.

            ## Правила для ИИ-агентов

            1. **Абстрактный интерфейс обязателен.** Определи `Abstract<Name>(ABC)` в слое `domain`.
            2. **Только доменные объекты.** Методы принимают и возвращают только объекты домена, а не ORM-модели или словари.
            3. **Конкретная реализация — в `infrastructure`.** SQLAlchemy, SQLite, Redis — только там.
            4. **Нет SQL в домене.** Любые запросы к БД — в слое `infrastructure`.
            5. **Тесты через `InMemory`-реализацию.** Тесты юнит-уровня используют `InMemory`-заглушки.
            """)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _good_logging(self) -> str:
        return textwrap.dedent("""\
            \"\"\"Good pattern: структурированное логирование через chutils.logger.\"\"\"
            from __future__ import annotations

            import logging

            logger = logging.getLogger(__name__)


            def process_order(order_id: int) -> bool:
                \"\"\"Обрабатывает заказ.

                Args:
                    order_id: Идентификатор заказа.

                Returns:
                    True если заказ обработан успешно.
                \"\"\"
                logger.info("Начало обработки заказа", extra={"order_id": order_id})
                try:
                    # ... бизнес-логика ...
                    logger.info("Заказ обработан", extra={"order_id": order_id, "status": "done"})
                    return True
                except Exception:
                    logger.exception("Ошибка обработки заказа", extra={"order_id": order_id})
                    return False
            """)

    def _bad_logging(self) -> str:
        return textwrap.dedent("""\
            \"\"\"Bad pattern: прямой print, нет контекста, нет структуры.\"\"\"


            def process_order(order_id):
                # Антипаттерн: print вместо logger, нет типов, нет контекста
                print(f"processing {order_id}")
                try:
                    pass  # ... логика ...
                except Exception as e:
                    print("ERROR:", e)   # Нет трассировки стека, нет структурных данных
            """)

    def _readme_logging(self) -> str:
        loggers = ", ".join(self._entities.loggers[:3]) if self._entities.loggers else "logger"
        return textwrap.dedent(f"""\
            # Logging (Логирование)

            В проекте обнаружены логгеры: **{loggers}**.

            ## Правила для ИИ-агентов

            1. **Всегда используй `logging.getLogger(__name__)`.** Имя логгера должно соответствовать модулю.
            2. **Никогда не используй `print()` для отладки.** Только `logger.debug()` / `logger.info()`.
            3. **Структурированный контекст через `extra={{}}`.** Передавай `order_id`, `user_id` и другие ключевые идентификаторы.
            4. **`logger.exception()` в `except`-блоках.** Это автоматически добавляет трассировку стека.
            5. **Не логируй секреты.** Пароли, токены, API-ключи не должны попадать в логи.
            """)

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------

    def _good_errors(self) -> str:
        name = self._entities.errors[0] if self._entities.errors else "DomainError"
        return textwrap.dedent(f"""\
            \"\"\"Good pattern: иерархия пользовательских исключений.\"\"\"
            from __future__ import annotations


            class AppError(Exception):
                \"\"\"Базовое исключение приложения.\"\"\"

                def __init__(self, message: str, *, hint: str = "") -> None:
                    super().__init__(message)
                    self.hint = hint


            class {name}(AppError):
                \"\"\"Ошибка на уровне домена. Не несёт деталей инфраструктуры.\"\"\"


            class ValidationError(AppError):
                \"\"\"Ошибка валидации входных данных.\"\"\"

                def __init__(self, field: str, reason: str) -> None:
                    super().__init__(f"Поле '{{field}}': {{reason}}")
                    self.field = field
                    self.reason = reason
            """)

    def _bad_errors(self) -> str:
        return textwrap.dedent("""\
            \"\"\"Bad pattern: сырые исключения без иерархии.\"\"\"


            def process(data: dict) -> None:  # type: ignore[type-arg]
                # Антипаттерн: raise Exception напрямую, нет иерархии, нет контекста
                if not data:
                    raise Exception("bad data")   # Не понятно какой тип ошибки
                if "id" not in data:
                    raise KeyError("id missing")   # Инфраструктурный тип в бизнес-логике
            """)

    def _readme_errors(self) -> str:
        names = ", ".join(self._entities.errors[:3]) if self._entities.errors else "AppError"
        return textwrap.dedent(f"""\
            # Errors / Exceptions (Исключения)

            В проекте обнаружены исключения: **{names}**.

            ## Правила для ИИ-агентов

            1. **Иерархия исключений.** Создай базовый класс `AppError(Exception)` и наследуй от него.
            2. **Доменные исключения — в `domain`.** Не используй `sqlite3.OperationalError` или `httpx.TimeoutException` в бизнес-логике.
            3. **Осмысленные сообщения.** Сообщение об ошибке должно отвечать на вопрос «что произошло» и «что делать».
            4. **Поле `hint`.** Добавляй подсказку для пользователя/разработчика через поле `hint`.
            5. **Никогда не raise Exception напрямую.** Всегда используй конкретный подкласс.
            """)

    # ------------------------------------------------------------------
    # DI
    # ------------------------------------------------------------------

    def _good_di(self) -> str:
        di_file = self._entities.di_files[0] if self._entities.di_files else "container"
        return textwrap.dedent(f"""\
            \"\"\"Good pattern: явный DI-контейнер через конструктор.\"\"\"
            # Файл: {di_file}.py
            from __future__ import annotations


            class Container:
                \"\"\"Компоновщик зависимостей приложения (Pure DI).

                Все зависимости создаются один раз и передаются через конструктор.
                \"\"\"

                def __init__(self) -> None:
                    # 1. Инфраструктура
                    from myapp.infrastructure.db import InMemoryUserRepository
                    self._user_repo = InMemoryUserRepository()

                    # 2. Use Cases (получают репозитории через DI)
                    from myapp.domain.use_cases import CreateUserUseCase
                    self.create_user_use_case = CreateUserUseCase(
                        repository=self._user_repo,
                    )
            """)

    def _bad_di(self) -> str:
        return textwrap.dedent("""\
            \"\"\"Bad pattern: God Object и Service Locator антипаттерн.\"\"\"
            # Антипаттерн: глобальный реестр сервисов (Service Locator)
            _REGISTRY: dict[str, object] = {}


            def register(name: str, instance: object) -> None:
                _REGISTRY[name] = instance


            def get(name: str) -> object:
                # Service Locator скрывает зависимости, усложняет тестирование
                return _REGISTRY[name]


            class SomeUseCase:
                def execute(self) -> None:
                    # Получает зависимость из глобального реестра — скрытая зависимость
                    repo = get("user_repo")   # type: ignore[assignment]
                    repo.save(...)  # type: ignore[union-attr]
            """)

    def _readme_di(self) -> str:
        files = ", ".join(self._entities.di_files[:3]) if self._entities.di_files else "container"
        return textwrap.dedent(f"""\
            # Dependency Injection (DI)

            В проекте обнаружены DI-файлы: **{files}**.

            ## Правила для ИИ-агентов

            1. **Явный конструктор-инжекция (Constructor Injection).** Все зависимости передаются через `__init__`.
            2. **Не используй Service Locator.** Глобальные реестры скрывают зависимости и усложняют тестирование.
            3. **Контейнер — только на верхнем уровне.** Бизнес-логика (`domain`) не знает о существовании контейнера.
            4. **Один контейнер на приложение.** Все зависимости собираются в одном месте (`container.py` / `di.py`).
            5. **Тестируй без контейнера.** В тестах передавай зависимости вручную или через `InMemory`-реализации.
            """)


# ---------------------------------------------------------------------------
# Генератор файлов банка примеров
# ---------------------------------------------------------------------------

class FewShotBankWriter:
    """Записывает сгенерированные шаблоны в целевую директорию.

    Args:
        output_dir: Путь к ``docs/ai_examples/`` в целевом проекте.
        force: Если True, перезаписывает существующие категории.
    """

    def __init__(self, output_dir: Path, *, force: bool = False) -> None:
        self._output_dir = output_dir
        self._force = force

    def write_category(
            self,
            category: str,
            good_code: str,
            bad_code: str,
            readme: str,
    ) -> bool:
        """Записывает файлы категории.

        Args:
            category: Название категории (папки).
            good_code: Содержимое ``good_pattern.py``.
            bad_code: Содержимое ``bad_pattern.py``.
            readme: Содержимое ``README.md``.

        Returns:
            True если файлы были записаны, False если категория пропущена.

        Raises:
            ValueError: При нарушении path traversal защиты.
        """
        cat_dir = self._resolve_safe(category)

        if cat_dir.exists() and not self._force:
            return False

        cat_dir.mkdir(parents=True, exist_ok=True)

        self._validate_python_syntax(good_code, f"{category}/good_pattern.py")
        self._validate_python_syntax(bad_code, f"{category}/bad_pattern.py")

        (cat_dir / "good_pattern.py").write_text(good_code, encoding="utf-8")
        (cat_dir / "bad_pattern.py").write_text(bad_code, encoding="utf-8")
        (cat_dir / "README.md").write_text(readme, encoding="utf-8")

        return True

    def _resolve_safe(self, category: str) -> Path:
        """Возвращает безопасный абсолютный путь к категории.

        Args:
            category: Имя категории.

        Returns:
            Абсолютный путь к директории категории.

        Raises:
            ValueError: Если category содержит попытку path traversal.
        """
        resolved = (self._output_dir / category).resolve()
        output_resolved = self._output_dir.resolve()
        if not str(resolved).startswith(str(output_resolved)):
            raise ValueError(
                f"Path traversal detected: категория '{category}' выходит за пределы '{output_resolved}'"
            )
        return resolved

    @staticmethod
    def _validate_python_syntax(code: str, filename: str) -> None:
        """Проверяет синтаксис Python-кода через ast.parse.

        Args:
            code: Исходный код Python.
            filename: Имя файла (для сообщения об ошибке).

        Raises:
            SyntaxError: Если код содержит синтаксические ошибки.
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(
                f"Синтаксическая ошибка в шаблоне '{filename}': {e}"
            ) from e


# ---------------------------------------------------------------------------
# Интеграция с манифестом GEMINI.md
# ---------------------------------------------------------------------------

GEMINI_BLOCK_START = "<!-- chutils:few-shot-start -->"
GEMINI_BLOCK_END = "<!-- chutils:few-shot-end -->"


def _build_gemini_block(categories: list[str]) -> str:
    """Строит Markdown-блок ссылок на few-shot банк.

    Args:
        categories: Список сгенерированных категорий.

    Returns:
        Строка с Markdown-блоком для вставки в GEMINI.md.
    """
    lines = [
        GEMINI_BLOCK_START,
        "",
        "## Few-shot примеры (AI Examples Bank)",
        "",
        "Банк примеров кода для обучения ИИ-агентов стандартам проекта.",
        "Сгенерирован командой `chutils dev generate-few-shot`.",
        "",
    ]
    for cat in categories:
        lines.append(f"- [{cat}](./docs/ai_examples/{cat}/README.md)")
    lines += ["", GEMINI_BLOCK_END, ""]
    return "\n".join(lines)


def update_gemini_manifest(project_root: Path, categories: list[str]) -> bool:
    """Обновляет или создаёт GEMINI.md с ссылками на few-shot банк.

    Args:
        project_root: Путь к корню целевого проекта.
        categories: Список созданных категорий.

    Returns:
        True если файл был создан или обновлён.
    """
    gemini_path = project_root / "GEMINI.md"
    block = _build_gemini_block(categories)

    if gemini_path.exists():
        content = gemini_path.read_text(encoding="utf-8")
        if GEMINI_BLOCK_START in content and GEMINI_BLOCK_END in content:
            # Заменяем существующий блок
            start_idx = content.index(GEMINI_BLOCK_START)
            end_idx = content.index(GEMINI_BLOCK_END) + len(GEMINI_BLOCK_END)
            # Захватываем завершающий перевод строки
            if end_idx < len(content) and content[end_idx] == "\n":
                end_idx += 1
            new_content = content[:start_idx] + block + content[end_idx:]
        else:
            # Добавляем блок в конец файла
            separator = "\n" if not content.endswith("\n") else ""
            new_content = content + separator + "\n" + block
        gemini_path.write_text(new_content, encoding="utf-8")
    else:
        # Создаём базовый GEMINI.md
        project_name = project_root.name
        base_content = textwrap.dedent(f"""\
            # {project_name}: Project Context for AI Agents

            Этот файл содержит контекст проекта для AI-агентов (Gemini, Cursor, Copilot и др.).

            ## Описание проекта

            > Заполните описание вашего проекта здесь.

            ## Архитектура

            > Опишите основные архитектурные решения здесь.

            """)
        gemini_path.write_text(base_content + "\n" + block, encoding="utf-8")

    return True


# ---------------------------------------------------------------------------
# Публичная точка входа
# ---------------------------------------------------------------------------

class _ConsoleProtocol(Protocol):
    """Минимальный интерфейс Rich Console для вывода сообщений."""

    def print(self, msg: str) -> None: ...


def generate_few_shot_bank(
        project_path: str,
        *,
        force: bool = False,
        console: _ConsoleProtocol | None = None,
) -> GenerationResult:
    """Генерирует банк few-shot примеров для целевого проекта.

    Анализирует архитектуру проекта, детектирует ключевые абстракции
    (Use Cases, репозитории, логгеры, исключения, DI-контейнеры) и
    создаёт параметризованные шаблоны ``docs/ai_examples/`` в корне
    целевого проекта.

    Args:
        project_path: Путь к корневой директории целевого проекта.
        force: Если True, существующие категории будут перезаписаны.
        console: Объект Rich Console для вывода статуса (опционально).

    Returns:
        GenerationResult с детализацией созданных и пропущенных категорий.

    Raises:
        FileNotFoundError: Если ``project_path`` не существует.
        ValueError: При нарушении path traversal защиты.
    """
    project_root = Path(project_path).resolve()
    if not project_root.exists():
        raise FileNotFoundError(f"Проект не найден: '{project_root}'")
    if not project_root.is_dir():
        raise FileNotFoundError(f"'{project_root}' — не директория")

    def _print(msg: str) -> None:
        if console is not None and hasattr(console, "print"):
            console.print(msg)

    _print(f"[bold cyan]🔍 Анализ проекта:[/bold cyan] {project_root}")

    # 1. Детектирование
    detector = ArchitectureDetector(project_root)
    entities = detector.detect()
    categories = list(entities.categories)

    if not categories:
        _print("[yellow]⚠ Архитектурные абстракции не обнаружены. Банк примеров не будет создан.[/yellow]")
        return GenerationResult()

    _print(f"[green]✓ Обнаружены категории:[/green] {', '.join(sorted(categories))}")

    # 2. Подготовка директории
    output_dir = project_root / "docs" / "ai_examples"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 3. Рендер и запись
    renderer = TemplateRenderer(entities)
    writer = FewShotBankWriter(output_dir, force=force)
    result = GenerationResult(output_dir=output_dir)

    for category in sorted(categories):
        good_code = renderer.render_good_pattern(category)
        bad_code = renderer.render_bad_pattern(category)
        readme = renderer.render_readme(category)

        written = writer.write_category(category, good_code, bad_code, readme)
        if written:
            result.created_categories.append(category)
            _print(f"  [green]✓[/green] Создана категория: [bold]{category}[/bold]")
        else:
            result.skipped_categories.append(category)
            _print(
                f"  [yellow]↷[/yellow] Пропущена (используйте --force для перезаписи): [bold]{category}[/bold]"
            )

    # 4. Обновление манифеста
    result.manifest_updated = update_gemini_manifest(project_root, result.created_categories)
    _print("[bold green]✓ GEMINI.md обновлён.[/bold green]")

    _print(
        f"\n[bold green]✅ Банк few-shot примеров создан:[/bold green] {output_dir}"
    )
    return result
