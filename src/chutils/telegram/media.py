"""Безопасное выкачивание медиа-файлов и документов из Telegram."""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any

from chutils.exceptions import ChutilsException, PathTraversalError
from chutils.fs import resolve_safe_path, safe_filename, ensure_dir

logger = logging.getLogger("chutils.telegram.media")


async def download_user_file(
    bot: Any,
    file_id: str,
    target_dir: str | Path,
    custom_filename: str | None = None,
    allow_unsafe_path: bool = False,
    max_size_bytes: int | None = None,
) -> Path:
    """Безопасно выкачивает файл из Telegram по `file_id` в указанную директорию `target_dir`.

    Args:
        bot: Экземпляр бота (aiogram.Bot или аналогичный с методом get_file/download_file) или bot_token (str).
        file_id: Уникальный идентификатор файла в Telegram API.
        target_dir: Целевая папка для сохранения.
        custom_filename: Желаемое имя файла. Если не указано, используется имя из Telegram или file_id.
        allow_unsafe_path: Если True, отключает строгую проверку Path Traversal (записывается предупреждение).
        max_size_bytes: Максимальный допустимый размер файла в байтах.

    Returns:
        Абсолютный путь (Path) к сохраненному файлу.

    Raises:
        PathTraversalError: При попытке выхода за границы target_dir (когда allow_unsafe_path=False).
        ChutilsException: При превышении max_size_bytes или ошибке загрузки.
    """
    target_dir_path = Path(target_dir).resolve()
    ensure_dir(target_dir_path)

    # 1. Запрос метаданных файла у Telegram Bot API
    file_path_on_server: str | None = None
    file_size: int | None = None

    if isinstance(bot, str):
        # Передан raw bot_token -> вызов через httpx / urllib
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.telegram.org/bot{bot}/getFile", params={"file_id": file_id})
            data = resp.json()
            if not data.get("ok"):
                raise ChutilsException(f"Ошибка Telegram API getFile: {data.get('description')}")
            result = data.get("result", {})
            file_path_on_server = result.get("file_path")
            file_size = result.get("file_size")
    elif hasattr(bot, "get_file"):
        # aiogram / python-telegram-bot
        tg_file = await bot.get_file(file_id)
        file_path_on_server = getattr(tg_file, "file_path", None)
        file_size = getattr(tg_file, "file_size", None)
    else:
        raise ChutilsException(f"Неподдерживаемый тип объекта bot: {type(bot).__name__}")

    # Проверка размера файла по метаданным
    if max_size_bytes is not None and file_size is not None and file_size > max_size_bytes:
        raise ChutilsException(
            f"Размер файла ({file_size} байт) превышает допустимый лимит ({max_size_bytes} байт)."
        )

    # 2. Определение имени файла
    raw_name = custom_filename or (Path(file_path_on_server).name if file_path_on_server else f"{file_id}.bin")

    if not allow_unsafe_path:
        sanitized_name = safe_filename(raw_name)
        destination_path = resolve_safe_path(sanitized_name, base_dir=target_dir_path)
    else:
        logger.warning(
            f"ВНИМАНИЕ: Защита Path Traversal отключена для скачивания файла '{raw_name}' (allow_unsafe_path=True)."
        )
        destination_path = (target_dir_path / raw_name).resolve()

    # 3. Скачивание содержимого файла
    if isinstance(bot, str):
        import httpx
        url = f"https://api.telegram.org/file/bot{bot}/{file_path_on_server}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            content = res.content
            if max_size_bytes is not None and len(content) > max_size_bytes:
                raise ChutilsException(f"Размер скачанного содержимого превысил лимит ({max_size_bytes} байт).")
            destination_path.write_bytes(content)
    elif hasattr(bot, "download_file"):
        # aiogram
        if file_path_on_server:
            await bot.download_file(file_path_on_server, destination=destination_path)
        else:
            await bot.download(file_id, destination=destination_path)

    return destination_path
