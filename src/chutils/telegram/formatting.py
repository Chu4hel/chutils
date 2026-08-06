from __future__ import annotations

import re

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


def split_message(text: str, max_length: int = 4096) -> list[str]:
    """Разбивает длинный текст на список валидных сообщений не превышающих max_length.

    Args:
        text: Исходный длинный текст.
        max_length: Максимальный размер одного сообщения (по умолчанию: 4096).

    Returns:
        Список чанков текста.
    """
    if not text:
        return []
    if len(text) <= max_length:
        return [text]

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
            # Если сама строка больше max_length, режем посимвольно
            while len(line) > max_length:
                chunks.append(line[:max_length])
                line = line[max_length:]
            current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
