from __future__ import annotations

import math
from typing import Any, Sequence, cast

ButtonSpec = tuple[str, str] | tuple[str, str, str | None] | dict[str, Any]


def _format_button(button: ButtonSpec) -> dict[str, str]:
    """Приводит спецификацию кнопки к единому словарю Telegram API InlineKeyboardButton."""
    if isinstance(button, dict):
        res: dict[str, str] = {"text": str(button.get("text", ""))}
        if "url" in button and button["url"]:
            res["url"] = str(button["url"])
        elif "callback_data" in button and button["callback_data"] is not None:
            res["callback_data"] = str(button["callback_data"])
        return res
    elif isinstance(button, (list, tuple)):
        text = str(button[0])
        res = {"text": text}
        if len(button) >= 3 and button[2]:
            res["url"] = str(button[2])
        elif len(button) >= 2 and button[1] is not None:
            res["callback_data"] = str(button[1])
        return res
    else:
        raise ValueError(f"Unsupported button format: {type(button)}")


def build_inline_keyboard(
    buttons: Sequence[ButtonSpec],
    buttons_per_row: int = 2,
    as_aiogram: bool = False,
) -> Any:
    """Создает сетку Inline-клавиатуры Telegram из списка кнопок.

    Args:
        buttons: Список спецификаций кнопок (кортежи или словари).
        buttons_per_row: Количество кнопок в одном ряду (по умолчанию 2).
        as_aiogram: Если True, возвращает aiogram InlineKeyboardMarkup (при наличии aiogram).

    Returns:
        Словарь вида {'inline_keyboard': [...]} или aiogram InlineKeyboardMarkup.
    """
    if buttons_per_row < 1:
        raise ValueError("buttons_per_row must be at least 1")

    formatted_buttons = [_format_button(btn) for btn in buttons]
    rows: list[list[dict[str, str]]] = []

    for i in range(0, len(formatted_buttons), buttons_per_row):
        rows.append(formatted_buttons[i : i + buttons_per_row])

    if as_aiogram:
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            aiogram_rows = []
            for row in rows:
                aiogram_row = []
                for btn in row:
                    if "url" in btn:
                        aiogram_row.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
                    else:
                        aiogram_row.append(InlineKeyboardButton(text=btn["text"], callback_data=btn.get("callback_data", "")))
                aiogram_rows.append(aiogram_row)
            return InlineKeyboardMarkup(inline_keyboard=aiogram_rows)
        except ImportError:
            pass

    return {"inline_keyboard": rows}


class PaginatorKeyboard:
    """Управляющий класс пагинации динамических Inline-клавиатур."""

    def __init__(
        self,
        items: Sequence[Any],
        per_page: int = 5,
        callback_prefix: str = "page",
    ) -> None:
        """Инициализирует PaginatorKeyboard.

        Args:
            items: Полный список элементов.
            per_page: Количество элементов на странице (по умолчанию 5).
            callback_prefix: Префикс callback_data для навигации.
        """
        self.items = items
        self.per_page = max(1, per_page)
        self.callback_prefix = callback_prefix

    @property
    def total_pages(self) -> int:
        """Возвращает общее количество страниц."""
        if not self.items:
            return 1
        return math.ceil(len(self.items) / self.per_page)

    def get_page_items(self, page: int = 1) -> list[Any]:
        """Возвращает срез элементов для указанной страницы (1-indexed).

        Args:
            page: Номер страницы (1..total_pages).

        Returns:
            Список элементов текущей страницы.
        """
        page = max(1, min(page, self.total_pages))
        start = (page - 1) * self.per_page
        end = start + self.per_page
        return list(self.items[start:end])

    def build_keyboard(
        self,
        page: int = 1,
        item_button_factory: Any = None,
        footer_buttons: Sequence[ButtonSpec] | None = None,
        buttons_per_row: int = 1,
        as_aiogram: bool = False,
    ) -> Any:
        """Строит готовую клавиатуру со срезом элементов и пагинационной панелью.

        Args:
            page: Номер запрашиваемой страницы.
            item_button_factory: Опциональная функция приведения элемента к ButtonSpec.
            footer_buttons: Дополнительные кнопки под панелью пагинации.
            buttons_per_row: Ряды элементов страницы.
            as_aiogram: Возвращать ли aiogram InlineKeyboardMarkup.

        Returns:
            Готовая клавиатура.
        """
        current_page = max(1, min(page, self.total_pages))
        page_items = self.get_page_items(current_page)

        buttons: list[ButtonSpec] = []
        for item in page_items:
            if item_button_factory:
                buttons.append(item_button_factory(item))
            elif isinstance(item, (tuple, dict)):
                buttons.append(cast(ButtonSpec, item))
            else:
                buttons.append((str(item), f"{self.callback_prefix}_item_{item}"))

        kb_dict = build_inline_keyboard(buttons, buttons_per_row=buttons_per_row, as_aiogram=False)
        rows: list[list[dict[str, str]]] = kb_dict["inline_keyboard"]

        # Панель навигации
        if self.total_pages > 1:
            nav_row: list[dict[str, str]] = []

            # Кнопка Назад
            if current_page > 1:
                nav_row.append({"text": "«", "callback_data": f"{self.callback_prefix}:{current_page - 1}"})
            else:
                nav_row.append({"text": " ", "callback_data": "noop"})

            # Индикатор страницы
            nav_row.append({"text": f"{current_page}/{self.total_pages}", "callback_data": "noop"})

            # Кнопка Вперед
            if current_page < self.total_pages:
                nav_row.append({"text": "»", "callback_data": f"{self.callback_prefix}:{current_page + 1}"})
            else:
                nav_row.append({"text": " ", "callback_data": "noop"})

            rows.append(nav_row)

        # Футер
        if footer_buttons:
            footer_kb = build_inline_keyboard(footer_buttons, buttons_per_row=len(footer_buttons), as_aiogram=False)
            rows.extend(footer_kb["inline_keyboard"])

        if as_aiogram:
            try:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                aiogram_rows = []
                for row in rows:
                    aiogram_row = []
                    for btn in row:
                        if "url" in btn:
                            aiogram_row.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
                        else:
                            aiogram_row.append(InlineKeyboardButton(text=btn["text"], callback_data=btn.get("callback_data", "")))
                    aiogram_rows.append(aiogram_row)
                return InlineKeyboardMarkup(inline_keyboard=aiogram_rows)
            except ImportError:
                pass

        return {"inline_keyboard": rows}
