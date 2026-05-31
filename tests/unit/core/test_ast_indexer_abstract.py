import ast
from pathlib import Path

from chutils.dev.ast_indexer import Indexer


def test_abstract_class_detection():
    """Тестирует корректность определения абстрактных классов."""
    code = """
import abc
from abc import ABC, abstractmethod

class MyAbstract(ABC):
    @abstractmethod
    def run(self):
        pass

class IndirectAbstract(MyAbstract):
    @abstractmethod
    def stop(self):
        pass

class NotAbstract:
    def hello(self):
        pass
"""
    # Создаем временный файл
    test_file = Path("test_abstract.py")
    test_file.write_text(code)

    try:
        # Используем текущую директорию как корень для теста
        indexer = Indexer(".")
        tree = ast.parse(code)

        # Находим символы
        symbols = indexer._extract_symbols(tree)

        # 1. MyAbstract должен быть абстрактным (наследует ABC)
        my_abs = next(s for s in symbols if s.name == "MyAbstract")
        assert my_abs.breadcrumbs.is_abstract is True

        # 2. IndirectAbstract должен быть абстрактным (имеет абстрактный метод)
        ind_abs = next(s for s in symbols if s.name == "IndirectAbstract")
        assert ind_abs.breadcrumbs.is_abstract is True

        # 3. NotAbstract не должен быть абстрактным
        not_abs = next(s for s in symbols if s.name == "NotAbstract")
        assert not_abs.breadcrumbs.is_abstract is False

    finally:
        if test_file.exists():
            test_file.unlink()


if __name__ == "__main__":
    test_abstract_class_detection()
    print("Abstract detection test passed!")
