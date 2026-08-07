"""Безопасное выкачивание и отправка медиа-файлов/документов в Telegram."""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any

from chutils.exceptions import ChutilsException, PathTraversalError
from chutils.fs import resolve_safe_path, safe_filename, ensure_dir, zip_folder, get_temp_file
from chutils.telegram.formatting import smart_truncate, escape_html, escape_markdown

logger = logging.getLogger("chutils.telegram.media")

MAX_TELEGRAM_BOT_FILE_SIZE = 50 * 1024 * 1024  # 50 MB limit for standard bot API


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
        if file_path_on_server:
            await bot.download_file(file_path_on_server, destination=destination_path)
        else:
            await bot.download(file_id, destination=destination_path)

    return destination_path


async def send_telegram_file(
    bot: Any,
    chat_id: int | str,
    file_path: str | Path,
    caption: str | None = None,
    parse_mode: str | None = None,
    allow_unsafe_path: bool = False,
    base_dir: str | Path | None = None,
) -> Any:
    """Безопасно отправляет файл или папку (с авто-упаковкой в ZIP) в Telegram.

    Args:
        bot: Экземпляр бота (aiogram.Bot) или raw bot_token (str).
        chat_id: Идентификатор чата или получателя.
        file_path: Путь к отправляемому файлу или директории.
        caption: Опциональная подпись к файлу (автоматически обрезается под 1024 символа).
        parse_mode: Режим разметки подписи ('HTML', 'MarkdownV2', etc.).
        allow_unsafe_path: Если True, отключает проверку Path Traversal.
        base_dir: Базовая директория для проверки выхода за границы.

    Returns:
        Объект отправленного сообщения Telegram API.

    Raises:
        PathTraversalError: Если файл находится за пределами base_dir.
        ChutilsException: При превышении лимита 50 МБ или ошибках отправки.
    """
    path_obj = Path(file_path)

    # 1. Проверка безопасности пути (Path Traversal Shield)
    if not allow_unsafe_path:
        path_obj = resolve_safe_path(path_obj, base_dir=base_dir)
    else:
        path_obj = path_obj.resolve()

    if not path_obj.exists():
        raise ChutilsException(f"Отправляемый файл или папка не существует: {path_obj}")

    # 2. Обработка папки: авто-упаковка в ZIP
    temp_zip_created: Path | None = None
    file_to_send = path_obj

    if path_obj.is_dir():
        import tempfile
        fd, temp_zip_path_str = tempfile.mkstemp(suffix=".zip", prefix=f"{safe_filename(path_obj.name)}_")
        os.close(fd)
        temp_zip_created = Path(temp_zip_path_str)
        file_to_send = zip_folder(path_obj, temp_zip_created)

    # 3. Проверка размера файла (лимит ботов Telegram 50 МБ)
    file_size = file_to_send.stat().st_size
    if file_size > MAX_TELEGRAM_BOT_FILE_SIZE:
        if temp_zip_created and temp_zip_created.exists():
            temp_zip_created.unlink(missing_ok=True)
        raise ChutilsException(
            f"Размер отправляемого файла ({file_size / (1024*1024):.2f} МБ) превышает лимит Telegram API (50 МБ)."
        )

    # 4. Безопасная обработка подписи (caption limit 1024 chars)
    formatted_caption: str | None = None
    if caption:
        formatted_caption = smart_truncate(caption, max_length=1024)

    # 5. Отправка файла
    try:
        if isinstance(bot, str):
            # Direct HTTP POST via httpx
            import httpx
            url = f"https://api.telegram.org/bot{bot}/sendDocument"
            data = {"chat_id": str(chat_id)}
            if formatted_caption:
                data["caption"] = formatted_caption
            if parse_mode:
                data["parse_mode"] = parse_mode

            async with httpx.AsyncClient() as client:
                with open(file_to_send, "rb") as f:
                    files = {"document": (file_to_send.name, f)}
                    resp = await client.post(url, data=data, files=files)
                    res_json = resp.json()
                    if not res_json.get("ok"):
                        raise ChutilsException(f"Ошибка Telegram sendDocument API: {res_json.get('description')}")
                    return res_json.get("result")
        elif hasattr(bot, "send_document"):
            # aiogram / python-telegram-bot
            try:
                from aiogram.types import FSInputFile
                input_file = FSInputFile(str(file_to_send))
                return await bot.send_document(
                    chat_id=chat_id,
                    document=input_file,
                    caption=formatted_caption,
                    parse_mode=parse_mode,
                )
            except ImportError:
                with open(file_to_send, "rb") as f:
                    return await bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        caption=formatted_caption,
                        parse_mode=parse_mode,
                    )
        else:
            raise ChutilsException(f"Неподдерживаемый тип объекта bot: {type(bot).__name__}")
    finally:
        if temp_zip_created and temp_zip_created.exists():
            temp_zip_created.unlink(missing_ok=True)
