from __future__ import annotations

import textwrap

from .models import DetectedEntities


class TemplateRenderer:
    """Рендерит параметризованные шаблоны Good/Bad паттернов и README для каждой категории.

    Args:
        entities: Найденные архитектурные сущности.
    """

    def __init__(self, entities: DetectedEntities) -> None:
        """Инициализирует TemplateRenderer.

        Args:
            entities: Обнаруженные в проекте сущности.
        """
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

            1. **Один Use Case — одна ответственность.** Желательно, чтобы каждый класс реализовывал ровно один бизнес-сценарий.
            2. **Явные Input/Output модели.** Используй `@dataclass(frozen=True)` для входных и выходных данных, чтобы структурировать обмен данными.
            3. **Инверсия зависимостей (DIP).** Use Case должен зависеть от абстракций (ABC / Protocol), а не от конкретных реализаций (БД, внешние сервисы).
            4. **Не обращайся к инфраструктуре напрямую.** Все операции с БД или внешними API должны осуществляться через интерфейсы (репозитории, шлюзы).
            5. **Типизация.** Рекомендуется аннотировать аргументы и возвращаемый тип метода `execute`.

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

            1. **Абстрактный интерфейс.** Рекомендуется определять `Abstract<Name>(ABC)` в слое `domain` для инверсии зависимостей.
            2. **Работа с доменными объектами.** Методы должны принимать и возвращать преимущественно объекты домена, а не ORM-модели или словари.
            3. **Инфраструктурные детали — отдельно.** Конкретные реализации (SQLAlchemy, Redis и др.) выноси в слой `infrastructure`.
            4. **Избегай SQL в домене.** Запросы к БД должны быть инкапсулированы внутри репозиториев в слое инфраструктуры.
            5. **Юнит-тестирование.** Для тестов юнит-уровня используй простые `InMemory`-реализации репозиториев.
            """)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _good_logging(self) -> str:
        return textwrap.dedent("""\
            \"\"\"Good pattern: структурированное логирование через chutils.logger.\"\"\"
            from __future__ import annotations

            from chutils import setup_logger

            logger = setup_logger(__name__)


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

            1. **Используй `chutils.setup_logger(__name__)`.** Это обеспечивает преднастроенный вывод и автоматическое маскирование секретов.
            2. **Избегай `print()` для логирования.** Для вывода информации используй логгер с подходящим уровнем (`debug`, `info`, `warning`, `error` и др.).
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

            1. **Иерархия исключений.** Рекомендуется создать базовый класс `AppError(Exception)` и наследовать от него пользовательские ошибки.
            2. **Доменные исключения — в `domain`.** Старайся не использовать инфраструктурные ошибки (например, `sqlite3.OperationalError` или `httpx.TimeoutException`) напрямую в бизнес-логике.
            3. **Осмысленные сообщения.** Сообщение об ошибке должно быть понятным и помогать локализовать проблему.
            4. **Поле `hint`.** При возможности добавляй подсказку для пользователя/разработчика через поле `hint`.
            5. **Избегай `raise Exception` напрямую.** Старайся использовать специализированные подклассы исключений.
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

            1. **Внедрение через конструктор (Constructor Injection).** Зависимости рекомендуется передавать через `__init__`.
            2. **Избегай Service Locator.** По возможности не используй глобальные реестры и синглтоны-локаторы, так как они скрывают зависимости.
            3. **Изоляция домена.** Бизнес-логика (`domain`) должна оставаться независимой от DI-контейнера или конкретных библиотек внедрения.
            4. **Компоновка на верхнем уровне.** Стремись собирать зависимости в одном месте (например, в `container.py` или `di.py`).
            5. **Тестирование.** Старайся писать юнит-тесты без создания глобального контейнера, передавая зависимости (или их InMemory-заглушки) вручную.
            """)
