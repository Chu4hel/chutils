"""Тесты функций валидации качества извлеченных данных (Extraction Quality Assertions)."""

from decimal import Decimal

import pytest
from pydantic import BaseModel

from chutils.scraping.testing.assertions import (
    assert_extraction_complete,
    assert_schema_match,
    assert_valid_price,
    assert_valid_url,
)


def test_assert_extraction_complete_single_dict() -> None:
    """Проверяет полноту извлечения полей одного словаря."""
    valid_item = {"title": "Ноутбук", "price": 50000, "url": "https://example.com/p/1"}
    assert_extraction_complete(valid_item, required_keys=["title", "price", "url"])

    # Ошибка: пропущен обязательный ключ
    with pytest.raises(AssertionError, match="Отсутствует обязательный ключ: 'price'"):
        assert_extraction_complete({"title": "Ноутбук"}, required_keys=["title", "price"])

    # Ошибка: значение None
    with pytest.raises(AssertionError, match="Поле 'price' содержит недопустимое пустое значение"):
        assert_extraction_complete({"title": "Ноутбук", "price": None})

    # Ошибка: пустая строка
    with pytest.raises(AssertionError, match="Поле 'title' содержит недопустимое пустое значение"):
        assert_extraction_complete({"title": "   ", "price": 100}, allow_empty_strings=False)

    # Пустая строка разрешена
    assert_extraction_complete({"title": "", "price": 100}, allow_empty_strings=True)


def test_assert_extraction_complete_list_of_dicts() -> None:
    """Проверяет полноту извлечения списка распарсенных элементов."""
    items = [
        {"id": 1, "title": "Товар 1"},
        {"id": 2, "title": "Товар 2"},
    ]
    assert_extraction_complete(items, required_keys=["id", "title"])

    # Ошибка во втором элементе
    bad_items = [
        {"id": 1, "title": "Товар 1"},
        {"id": 2, "title": None},
    ]
    with pytest.raises(AssertionError, match="Элемент \\[1\\]: Поле 'title' содержит недопустимое пустое значение"):
        assert_extraction_complete(bad_items)


def test_assert_valid_url() -> None:
    """Проверяет валидацию извлеченных ссылок."""
    assert_valid_url("https://example.com/products/item?ref=1")
    assert_valid_url("http://127.0.0.1:8000/page")

    # Ошибка: относительный путь
    with pytest.raises(AssertionError, match="Относительный URL без схемы"):
        assert_valid_url("/products/item")

    # Ошибка: недопустимая схема
    with pytest.raises(AssertionError, match="Недопустимая схема URL"):
        assert_valid_url("ftp://files.example.com")

    # Ошибка: отсутствует домен / хост
    with pytest.raises(AssertionError, match="Отсутствует сетевой хост"):
        assert_valid_url("https://")


def test_assert_valid_price() -> None:
    """Проверяет валидацию цен (числа, строки с валютой, Decimal)."""
    assert_valid_price(199.99)
    assert_valid_price(100)
    assert_valid_price(Decimal("1500.50"))
    assert_valid_price("1 499,90 ₽")
    assert_valid_price("$29.99")

    # Ошибка: отрицательная цена
    with pytest.raises(AssertionError, match="Цена меньше минимального порога"):
        assert_valid_price(-10)

    # Ошибка: превышение максимального порога
    with pytest.raises(AssertionError, match="Цена превышает максимальный порог"):
        assert_valid_price(100000, max_value=50000)

    # Ошибка: нечисловой мусор
    with pytest.raises(AssertionError, match="Не удалось распознать числовое значение цены"):
        assert_valid_price("Нет в наличии")


def test_assert_schema_match() -> None:
    """Проверяет валидацию извлеченных данных по Pydantic схеме."""
    class ProductItem(BaseModel):
        id: int
        name: str
        price: float

    valid_dict = {"id": 1, "name": "Телефон", "price": 29990.0}
    assert_schema_match(valid_dict, ProductItem)

    valid_list = [
        {"id": 1, "name": "Телефон", "price": 29990.0},
        {"id": 2, "name": "Чехол", "price": 990.0},
    ]
    assert_schema_match(valid_list, ProductItem)

    # Ошибка: несоответствие типа поля
    invalid_dict = {"id": "не число", "name": "Телефон", "price": 29990.0}
    with pytest.raises(AssertionError, match="Ошибка валидации схемы ProductItem"):
        assert_schema_match(invalid_dict, ProductItem)
