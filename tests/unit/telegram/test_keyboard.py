import pytest

from chutils.telegram.keyboard import build_inline_keyboard, PaginatorKeyboard


def test_build_inline_keyboard_tuples():
    """Проверяет создание сетки кнопок из кортежей."""
    buttons = [
        ("Button 1", "cb_1"),
        ("Button 2", "cb_2"),
        ("Button 3", "cb_3"),
    ]
    kb = build_inline_keyboard(buttons, buttons_per_row=2)

    assert "inline_keyboard" in kb
    rows = kb["inline_keyboard"]
    assert len(rows) == 2
    assert len(rows[0]) == 2
    assert len(rows[1]) == 1
    assert rows[0][0] == {"text": "Button 1", "callback_data": "cb_1"}


def test_build_inline_keyboard_dicts_and_urls():
    """Проверяет поддержку словарей и URL кнопок."""
    buttons = [
        {"text": "Site", "url": "https://example.com"},
        {"text": "Action", "callback_data": "act_1"},
    ]
    kb = build_inline_keyboard(buttons, buttons_per_row=1)

    rows = kb["inline_keyboard"]
    assert len(rows) == 2
    assert rows[0][0] == {"text": "Site", "url": "https://example.com"}
    assert rows[1][0] == {"text": "Action", "callback_data": "act_1"}


def test_paginator_keyboard():
    """Проверяет пагинацию PaginatorKeyboard."""
    items = [f"Item {i}" for i in range(1, 13)]  # 12 элементов = 3 страницы по 5 элементов
    paginator = PaginatorKeyboard(items, per_page=5, callback_prefix="catalog")

    assert paginator.total_pages == 3
    assert len(paginator.get_page_items(1)) == 5
    assert len(paginator.get_page_items(3)) == 2

    # Построение клавиатуры для 1-й страницы
    kb1 = paginator.build_keyboard(page=1, footer_buttons=[("Close", "close_act")])
    rows1 = kb1["inline_keyboard"]
    # 5 кнопок элементов + 1 ряд навигации + 1 ряд футера = 7 рядов
    assert len(rows1) == 7
    # Проверка панели навигации
    nav_row = rows1[5]
    assert nav_row[0]["text"] == " "
    assert nav_row[1]["text"] == "1/3"
    assert nav_row[2]["text"] == "»"
    assert nav_row[2]["callback_data"] == "catalog:2"
