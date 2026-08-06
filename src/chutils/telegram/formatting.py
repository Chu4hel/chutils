from __future__ import annotations

import re
from typing import Literal

# Спецсимволы MarkdownV2 по спецификации Telegram API
_MARKDOWN_V2_ESCAPES = r"\_*[]()~`>#+-=|{}.!"
_MARKDOWN_V1_ESCAPES = r"_*`["

_HTML_ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
}


def escape_markdown(text: str, version: int = 2) -> str:
    """Экранирует специальные символы в тексте для парс-режима Markdown в Telegram.

    Args:
        text: Исходный текст.
        version: Версия синтаксиса Markdown (1 или 2, по умолчанию: 2).

    Returns:
        Экранированный текст.
    """
    if not text:
        return ""

    if version == 1:
        pattern = f"([{re.escape(_MARKDOWN_V1_ESCAPES)}])"
        return re.sub(pattern, r"\\\1", text)

    pattern = f"([{re.escape(_MARKDOWN_V2_ESCAPES)}])"
    return re.sub(pattern, r"\\\1", text)


def escape_html(text: str) -> str:
    """Экранирует специальные символы в тексте для парс-режима HTML в Telegram.

    Args:
        text: Исходный текст.

    Returns:
        Экранированный HTML текст.
    """
    if not text:
        return ""
    return "".join(_HTML_ESCAPES.get(c, c) for c in text)


def smart_truncate(text: str, max_length: int = 4096, suffix: str = "...") -> str:
    """Безопасно обрезает текст до max_length с закрытием кодовых блоков (```).

    Args:
        text: Исходный текст сообщения.
        max_length: Максимальная допустимая длина (по умолчанию 4096).
        suffix: Суффикс для обрезанного сообщения.

    Returns:
        Обрезанный валидный текст.
    """
    if len(text) <= max_length:
        return text

    target_len = max_length - len(suffix)
    truncated = text[:target_len]

    # Если мы разрезали внутри кодового блока (нечетное количество ```)
    code_blocks = len(re.findall(r"```", truncated))
    if code_blocks % 2 != 0:
        truncated += "\n```"

    return truncated + suffix


def split_message(
    text: str,
    max_length: int = 4096,
    mode: Literal["paragraph", "line", "word", "char"] = "line",
) -> list[str]:
    """Разбивает длинный текст на список валидных сообщений не превышающих max_length.

    Args:
        text: Исходный длинный текст.
        max_length: Максимальный размер одного сообщения (по умолчанию: 4096).
        mode: Стратегия разбиения:
            - 'paragraph': сплит по абзацам (\\n\\n)
            - 'line': сплит по строкам (\\n, по умолчанию)
            - 'word': сплит по словам (пробелам)
            - 'char': жесткий сплит посимвольно

    Returns:
        Список чанков текста.
    """
    if not text:
        return []
    if len(text) <= max_length:
        return [text]

    if mode == "char":
        return [text[i : i + max_length] for i in range(0, len(text), max_length)]

    if mode == "paragraph":
        delimiter = "\n\n"
        units = text.split("\n\n")
    elif mode == "word":
        delimiter = " "
        units = text.split(" ")
    else:  # line
        return _split_by_lines(text, max_length)

    chunks: list[str] = []
    current_chunk = ""

    for idx, unit in enumerate(units):
        sep = delimiter if idx > 0 and current_chunk else ""
        item = sep + unit

        if len(current_chunk) + len(item) <= max_length:
            current_chunk += item
        else:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            # Если элемент сам по себе превышает max_length, используем fallback
            if len(unit) > max_length:
                sub_chunks = _split_by_lines(unit, max_length) if mode == "paragraph" else split_message(unit, max_length, mode="char")
                chunks.extend(sub_chunks[:-1])
                current_chunk = sub_chunks[-1]
            else:
                current_chunk = unit

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _split_by_lines(text: str, max_length: int) -> list[str]:
    """Вспомогательный сплиттер по строкам."""
    chunks: list[str] = []
    lines = text.splitlines(keepends=True)
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) <= max_length:
            current_chunk += line
        else:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            while len(line) > max_length:
                chunks.append(line[:max_length])
                line = line[max_length:]
            current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
