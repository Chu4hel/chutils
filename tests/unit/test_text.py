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
