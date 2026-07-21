import asyncio
import threading
import time

import pytest

from chutils.di import Container, provide, inject, Inject
from chutils.exceptions import DependencyNotFoundError, DependencyResolutionError


# Вспомогательные классы для тестирования
class DummyDependencyC:
    def __init__(self) -> None:
        self.value = "C"


class DummyDependencyB:
    def __init__(self, c: DummyDependencyC) -> None:
        self.c = c
        self.value = "B"


class DummyDependencyA:
    def __init__(self, b: DummyDependencyB) -> None:
        self.b = b
        self.value = "A"


class CycleA:
    def __init__(self, b: "CycleB") -> None:
        self.b = b


class CycleB:
    def __init__(self, a: CycleA) -> None:
        self.a = a


def test_basic_registration_and_resolution():
    """Тест простой регистрации и ручного разрешения зависимостей."""
    container = Container()

    # 1. Регистрация класса напрямую
    container.register(DummyDependencyC)
    assert container.has_provider(DummyDependencyC) is True

    c_instance = container.resolve(DummyDependencyC)
    assert isinstance(c_instance, DummyDependencyC)
    assert c_instance.value == "C"

    # 2. Регистрация интерфейса/класса с фабрикой
    container.register(str, provider=lambda: "Hello Factory")
    assert container.resolve(str) == "Hello Factory"


def test_scopes():
    """Тест времени жизни (scopes) зависимостей: singleton vs transient."""
    container = Container()

    class Counter:
        def __init__(self) -> None:
            self.count = 0

    # Singleton scope (по умолчанию)
    container.register(Counter, scope="singleton")
    inst1 = container.resolve(Counter)
    inst2 = container.resolve(Counter)
    assert inst1 is inst2

    inst1.count += 1
    assert inst2.count == 1

    # Transient scope
    container.clear()
    container.register(Counter, scope="transient")
    inst3 = container.resolve(Counter)
    inst4 = container.resolve(Counter)
    assert inst3 is not inst4

    inst3.count += 1
    assert inst4.count == 0


def test_recursive_resolution():
    """Тест рекурсивного разрешения графа зависимостей."""
    container = Container()
    container.register(DummyDependencyC)
    container.register(DummyDependencyB)
    container.register(DummyDependencyA)

    a = container.resolve(DummyDependencyA)
    assert isinstance(a, DummyDependencyA)
    assert isinstance(a.b, DummyDependencyB)
    assert isinstance(a.b.c, DummyDependencyC)
    assert a.b.c.value == "C"


def test_cyclic_dependency():
    """Проверка возбуждения исключения при циклической зависимости."""
    container = Container()

    container.register(CycleA)
    container.register(CycleB)

    with pytest.raises(DependencyResolutionError) as exc_info:
        container.resolve(CycleA)
    assert "Обнаружена циклическая зависимость" in str(exc_info.value)


def test_provide_decorator():
    """Проверка регистрации через декоратор @provide."""
    container = Container()

    @provide(container=container)
    class DecoratedService:
        def __init__(self) -> None:
            self.val = 42

    @provide(container=container)
    def factory_function() -> str:
        return "FactoryDeco"

    assert container.has_provider(DecoratedService) is True
    assert container.has_provider(str) is True

    assert container.resolve(DecoratedService).val == 42
    assert container.resolve(str) == "FactoryDeco"


def test_provide_decorator_missing_return_type():
    """Проверка ошибки при использовании @provide на функции без возвращаемого типа."""
    container = Container()

    with pytest.raises(DependencyResolutionError) as exc_info:
        @provide(container=container)
        def invalid_factory():
            return "no_type"

    assert "отсутствует аннотация возвращаемого типа" in str(exc_info.value)


def test_inject_decorator_sync():
    """Проверка автоматического внедрения зависимостей в синхронные функции."""
    container = Container()
    container.register(DummyDependencyC)

    @inject(container=container)
    def my_handler(prefix: str, c: DummyDependencyC = Inject()):
        return f"{prefix}_{c.value}"

    # Без явной передачи зависимости
    res = my_handler("test")
    assert res == "test_C"

    # С явной передачей зависимости (overriding)
    custom_c = DummyDependencyC()
    custom_c.value = "Custom"
    res_override = my_handler("test", c=custom_c)
    assert res_override == "test_Custom"


@pytest.mark.asyncio
async def test_inject_decorator_async():
    """Проверка автоматического внедрения зависимостей в асинхронные функции."""
    container = Container()
    container.register(DummyDependencyC)

    @inject(container=container)
    async def my_async_handler(c: DummyDependencyC = Inject()):
        await asyncio.sleep(0.001)
        return c.value

    assert await my_async_handler() == "C"


def test_inject_by_type_without_marker():
    """Проверка авто-внедрения по типу без использования маркера Inject()."""
    container = Container()
    container.register(DummyDependencyC)

    # c не имеет маркера Inject(), но имеет тип DummyDependencyC, который есть в контейнере
    @inject(container=container)
    def handle(c: DummyDependencyC):
        return c.value

    assert handle() == "C"


def test_thread_safety_singleton():
    """Проверяет безопасность ленивого создания Singleton в многопоточной среде."""
    container = Container()

    class SlowInitDependency:
        def __init__(self) -> None:
            # Имитируем тяжелую инициализацию
            time.sleep(0.1)
            self.thread_id = threading.get_ident()

    container.register(SlowInitDependency, scope="singleton")

    instances = []
    errors = []

    def task():
        try:
            instances.append(container.resolve(SlowInitDependency))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=task) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Ошибки при разрешении: {errors}"
    assert len(instances) == 10
    # Все инстансы должны ссылаться на один и тот же объект
    first = instances[0]
    for inst in instances:
        assert inst is first


def test_dependency_not_found():
    """Проверка правильного исключения при отсутствии зависимости."""
    import abc
    class AbstractService(abc.ABC):
        @abc.abstractmethod
        def do_something(self):
            pass

    container = Container()

    with pytest.raises(DependencyNotFoundError) as exc_info:
        container.resolve(AbstractService)
    assert "не зарегистрирована в контейнере" in str(exc_info.value)


def test_autowiring_unregistered_concrete_class():
    """Проверка авто-регистрации конкретного класса 'на лету' (auto-wiring)."""
    container = Container()

    # Класс DummyDependencyC не зарегистрирован явно в контейнере,
    # но контейнер должен зарегистрировать его автоматически как singleton.
    c = container.resolve(DummyDependencyC)
    assert isinstance(c, DummyDependencyC)
    assert c.value == "C"

    # Повторный резолв должен вернуть тот же инстанс
    c2 = container.resolve(DummyDependencyC)
    assert c is c2


def test_inject_no_parens():
    """Тест работы декоратора @inject без скобок."""
    from chutils.di import default_container
    
    # Регистрируем в глобальный контейнер
    default_container.register(DummyDependencyC)
    
    @inject
    def handle_global(c: DummyDependencyC = Inject()):
        return c.value
        
    assert handle_global() == "C"
    default_container.clear()


def test_string_dependencies():
    """Тест поддержки строковых имен и forward refs при разрешении зависимостей."""
    container = Container()

    # 1. Регистрация строкового имени напрямую
    container.register("Repository", lambda: "DatabaseRepository")
    assert container.resolve("Repository") == "DatabaseRepository"

    # 2. Разрешение зависимости с типом класса, если зарегистрирована строка
    class RepositoryClass:
        pass
        
    container.register("RepositoryClass", lambda: RepositoryClass())
    resolved = container.resolve(RepositoryClass)
    assert isinstance(resolved, RepositoryClass)

    # 3. Разрешение строковой аннотации в сигнатуре класса (forward ref)
    class Service:
        def __init__(self, repo: "Repository") -> None:
            self.repo = repo

    container.register(Service)
    service = container.resolve(Service)
    assert service.repo == "DatabaseRepository"

