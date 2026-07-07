import pytest

from chutils.text import natsort_key

def test_natsort_key_basic():
    """Проверяет базовую естественную сортировку строк с числами."""
    items = ["item 10", "item 2", "item 1", "item 21"]
    sorted_items = sorted(items, key=natsort_key)
    assert sorted_items == ["item 1", "item 2", "item 10", "item 21"]


def test_natsort_key_no_numbers():
    """Проверяет сортировку строк без чисел (регистронезависимо)."""
    items = ["Banana", "apple", "Cherry"]
    sorted_items = sorted(items, key=natsort_key)
    assert sorted_items == ["apple", "Banana", "Cherry"]


def test_natsort_key_multiple_numbers():
    """Проверяет сортировку строк с несколькими числами."""
    items = ["item 2 version 10", "item 2 version 2", "item 1 version 100"]
    sorted_items = sorted(items, key=natsort_key)
    assert sorted_items == [
        "item 1 version 100",
        "item 2 version 2",
        "item 2 version 10"
    ]


def test_natsort_key_leading_zeros():
    """Проверяет поведение при наличии ведущих нулей."""
    # "02" и "2" преобразуются в int(2).
    # Но для полной надежности проверим, что они сортируются корректно и не падают.
    items = ["item 02", "item 1", "item 2"]
    sorted_items = sorted(items, key=natsort_key)
    # Так как "02" и "2" равны по числовому значению, стабильная сортировка сохранит их порядок.
    # Главное, что "item 1" идет перед ними.
    assert sorted_items[0] == "item 1"
    assert set(sorted_items[1:]) == {"item 02", "item 2"}


def test_is_significant_difference_identical():
    """Проверяет сравнение идентичных строк."""
    from chutils.text import is_significant_difference
    # Идентичные строки -> similarity = 100%, разница не значительна
    assert is_significant_difference("Привет мир", "Привет мир", threshold=0.9) is False


def test_is_significant_difference_minor():
    """Проверяет сравнение строк с незначительными различиями."""
    from chutils.text import is_significant_difference
    # Небольшие различия -> схожесть высокая (например, > 90%).
    # Разница не должна быть значительной для порога 0.8
    assert is_significant_difference("Привет мир!", "Привет мир.", threshold=0.8) is False


def test_is_significant_difference_major():
    """Проверяет сравнение строк со значительными различиями."""
    from chutils.text import is_significant_difference
    # Абсолютно разные строки -> similarity низкая, разница значительна
    assert is_significant_difference("Привет мир", "Пока луна", threshold=0.5) is True


def test_is_significant_difference_no_rapidfuzz(monkeypatch):
    """Проверяет поведение, когда библиотека rapidfuzz не установлена."""
    import chutils.text
    from chutils.exceptions import OptionalDependencyError
    # Симулируем отсутствие rapidfuzz
    monkeypatch.setattr(chutils.text, "_HAS_RAPIDFUZZ", False)

    with pytest.raises(OptionalDependencyError) as exc_info:
        chutils.text.is_significant_difference("a", "b")

    assert "chutils[text]" in str(exc_info.value)
