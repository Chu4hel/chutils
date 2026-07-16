import asyncio
import functools
import inspect
import threading
from typing import Any, TypeVar
from collections.abc import Callable

from chutils.exceptions import DependencyNotFoundError, DependencyResolutionError

T = TypeVar("T")


class InjectMarker:
    """Маркер для инъекции зависимостей через значения по умолчанию."""
    pass


def Inject() -> Any:
    """Маркер инъекции зависимостей (в стиле FastAPI / Depends).
    
    Пример:
        def handle(service: MyService = Inject()):
            ...

    Returns:
        Маркерный объект InjectMarker.
    """
    return InjectMarker()


class Container:
    """
    Легковесный IoC/DI контейнер.
    
    Поддерживает:
    - Синглтоны (Singleton) и переходные зависимости (Transient).
    - Автоматическое рекурсивное разрешение зависимостей по Type Hints.
    - Декларативную регистрацию через декоратор @provide.
    - Внедрение через декоратор @inject и маркер Inject().
    - Потокобезопасность.
    """

    def __init__(self) -> None:
        """Инициализирует DI-контейнер."""
        # Реестр провайдеров: {type: (provider_callable, scope)}
        self._providers: dict[type[Any], tuple[Callable[..., Any], str]] = {}
        # Кэш инстансов для scope="singleton": {type: instance}
        self._instances: dict[type[Any], Any] = {}
        # Блокировка для обеспечения потокобезопасности
        self._lock = threading.Lock()
        # Потокобезопасный контекст для стека разрешения зависимостей
        self._local = threading.local()

    @property
    def _resolving_stack(self) -> list[type[Any]]:
        if not hasattr(self._local, "stack"):
            self._local.stack = []
        return self._local.stack  # type: ignore[no-any-return]

    def register(
            self,
            dependency_type: type[Any],
            provider: Callable[..., Any] | None = None,
            scope: str = "singleton"
    ) -> None:
        """
        Зарегистрировать зависимость.
        
        Args:
            dependency_type: Класс или интерфейс (тип зависимости).
            provider: Функция-фабрика или класс для создания объекта.
                Если не указан, используется сам dependency_type.
            scope: Время жизни зависимости: "singleton" или "transient".
        """
        if scope not in ("singleton", "transient"):
            raise DependencyResolutionError(
                f"Неподдерживаемый scope: '{scope}'. Допустимы только 'singleton' или 'transient'."
            )

        actual_provider = provider
        if actual_provider is None:
            if not inspect.isclass(dependency_type):
                raise DependencyResolutionError(
                    f"Невозможно зарегистрировать тип '{dependency_type}' без провайдера, так как он не является классом."
                )
            actual_provider = dependency_type

        with self._lock:
            self._providers[dependency_type] = (actual_provider, scope)
            # Если объект уже был закэширован, удаляем его для корректного переопределения
            self._instances.pop(dependency_type, None)

    def has_provider(self, dependency_type: type[Any]) -> bool:
        """Проверить, зарегистрирован ли провайдер для данного типа.

        Args:
            dependency_type: Класс/тип зависимости.

        Returns:
            True, если провайдер зарегистрирован, иначе False.
        """
        with self._lock:
            return dependency_type in self._providers

    def resolve(self, dependency_type: type[T]) -> T:
        """Разрешить зависимость (найти провайдер, разрешить его аргументы и вернуть инстанс).

        Args:
            dependency_type: Класс/тип запрашиваемой зависимости.

        Returns:
            Разрешенный экземпляр запрашиваемой зависимости.
        """
        # Предотвращение циклических зависимостей
        if dependency_type in self._resolving_stack:
            cycle = " -> ".join(cls.__name__ for cls in self._resolving_stack + [dependency_type])
            raise DependencyResolutionError(
                f"Обнаружена циклическая зависимость: {cycle}"
            )

        self._resolving_stack.append(dependency_type)

        try:
            # 1. Получаем провайдер
            with self._lock:
                provider_info = self._providers.get(dependency_type)

            # Автоматическая регистрация конкретных классов (Auto-wiring)
            if provider_info is None:
                if inspect.isclass(dependency_type) and not inspect.isabstract(dependency_type):
                    # Проверяем, что класс не является стандартным примитивом
                    if dependency_type.__module__ != "builtins":
                        self.register(dependency_type)
                        with self._lock:
                            provider_info = self._providers.get(dependency_type)

            if provider_info is None:
                raise DependencyNotFoundError(
                    f"Зависимость '{dependency_type.__name__ if hasattr(dependency_type, '__name__') else dependency_type}' не зарегистрирована в контейнере."
                )

            provider, scope = provider_info

            # 2. Если singleton, проверяем кэш инстансов
            if scope == "singleton":
                with self._lock:
                    if dependency_type in self._instances:
                        return self._instances[dependency_type]  # type: ignore[no-any-return]

            # 3. Разрешаем аргументы провайдера
            resolved_args: dict[str, Any] = {}

            # Получаем типы параметров с разрешением строковых аннотаций
            import typing
            try:
                if inspect.isclass(provider):
                    type_hints = typing.get_type_hints(provider.__init__)
                else:
                    type_hints = typing.get_type_hints(provider)
            except Exception:
                type_hints = {}

            # Анализируем сигнатуру
            if inspect.isclass(provider):
                # Если провайдер класс, инспектируем __init__
                sig = inspect.signature(provider.__init__)
                # Пропускаем 'self'
                parameters = list(sig.parameters.values())[1:]
            else:
                # Если провайдер - функция-фабрика
                sig = inspect.signature(provider)
                parameters = list(sig.parameters.values())

            for param in parameters:
                # Пропускаем параметры переменной длины (*args, **kwargs)
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                param_name = param.name
                # Берем тип из type_hints, если он там есть, иначе из param.annotation
                param_type = type_hints.get(param_name, param.annotation)

                # Проверяем маркер Inject() или отсутствие дефолтного значения
                is_explicit_inject = isinstance(param.default, InjectMarker)
                has_no_default = param.default is inspect.Parameter.empty

                if is_explicit_inject or has_no_default:
                    if param_type is inspect.Parameter.empty or isinstance(param_type, str):
                        raise DependencyResolutionError(
                            f"Невозможно разрешить параметр '{param_name}' для провайдера '{provider}': отсутствует аннотация типа или тип не разрешен."
                        )
                    # Рекурсивно разрешаем параметр
                    resolved_args[param_name] = self.resolve(param_type)
                elif param.default is not inspect.Parameter.empty:
                    # Используем значение по умолчанию
                    resolved_args[param_name] = param.default

            # 4. Создаем экземпляр
            if scope == "singleton":
                with self._lock:
                    # Double-checked locking
                    if dependency_type in self._instances:
                        return self._instances[dependency_type]  # type: ignore[no-any-return]

                    instance = provider(**resolved_args)
                    self._instances[dependency_type] = instance
                    return instance  # type: ignore[no-any-return]
            else:
                return provider(**resolved_args)  # type: ignore[no-any-return]

        finally:
            self._resolving_stack.pop()

    def clear(self) -> None:
        """Очистить все зарегистрированные провайдеры и закэшированные инстансы."""
        with self._lock:
            self._providers.clear()
            self._instances.clear()
            self._resolving_stack.clear()


# Глобальный контейнер по умолчанию
default_container = Container()


def provide(scope: str = "singleton", container: Container | None = None) -> Callable[[Any], Any]:
    """Декоратор для декларативной регистрации класса или функции-фабрики в контейнере.
    
    Пример:
        @provide()
        class DatabaseService:
            ...
            
        @provide()
        def create_connection() -> Connection:
            return Connection(...)

    Args:
        scope: Время жизни зависимости ("singleton" или "transient").
        container: Контейнер для регистрации (по умолчанию глобальный).

    Returns:
        Декоратор для регистрации класса или фабрики.
    """
    target_container = container or default_container

    def decorator(cls_or_func: Any) -> Any:
        if inspect.isclass(cls_or_func):
            target_container.register(cls_or_func, scope=scope)
        else:
            sig = inspect.signature(cls_or_func)
            return_type = sig.return_annotation
            if return_type is inspect.Signature.empty:
                raise DependencyResolutionError(
                    f"Не удалось зарегистрировать провайдер '{cls_or_func.__name__}': отсутствует аннотация возвращаемого типа."
                )
            target_container.register(return_type, provider=cls_or_func, scope=scope)
        return cls_or_func

    return decorator


def inject(container: Container | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Декоратор для автоматического внедрения зависимостей в аргументы функции.
    
    Пример:
        @inject()
        def process_data(db: DatabaseService = Inject()):
            db.query(...)

    Args:
        container: Контейнер для разрешения зависимостей (по умолчанию глобальный).

    Returns:
        Декоратор, автоматически подставляющий зависимости в аргументы функции.
    """
    target_container = container or default_container

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(func)
        is_async = asyncio.iscoroutinefunction(func)

        # Вычисляем параметры, которые требуют инъекции
        injectable_params: list[tuple[str, inspect.Parameter]] = []
        for name, param in sig.parameters.items():
            is_explicit_inject = isinstance(param.default, InjectMarker)
            has_annotation = param.annotation is not inspect.Parameter.empty

            # Инъецируем, если:
            # 1. Есть явный маркер Inject()
            # 2. Или параметр не имеет значения по умолчанию, но его тип зарегистрирован в контейнере
            if is_explicit_inject:
                injectable_params.append((name, param))
            elif param.default is inspect.Parameter.empty and has_annotation:
                if target_container.has_provider(param.annotation) or (
                        inspect.isclass(param.annotation) and not inspect.isabstract(param.annotation)
                ):
                    injectable_params.append((name, param))

        if not injectable_params:
            return func

        if is_async:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                bound = sig.bind_partial(*args, **kwargs)
                bound_keys = set(bound.arguments.keys())

                for name, param in injectable_params:
                    # Инъецируем только если аргумент не был передан явно или передан как маркер
                    if name not in bound_keys or isinstance(bound.arguments[name], InjectMarker):
                        bound.arguments[name] = target_container.resolve(param.annotation)

                return await func(*bound.args, **bound.kwargs)
        else:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                bound = sig.bind_partial(*args, **kwargs)
                bound_keys = set(bound.arguments.keys())

                for name, param in injectable_params:
                    if name not in bound_keys or isinstance(bound.arguments[name], InjectMarker):
                        bound.arguments[name] = target_container.resolve(param.annotation)

                return func(*bound.args, **bound.kwargs)

        return wrapper

    return decorator
