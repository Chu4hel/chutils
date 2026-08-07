"""Unit-тесты для send_telegram_file, авто-упаковки директорий и обрезки подписей."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from chutils.exceptions import PathTraversalError
from chutils.telegram.media import send_telegram_file


@pytest.mark.asyncio
async def test_send_telegram_file_mock_bot(tmp_path: Path):
    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"pdf_content_data")

    mock_bot = MagicMock()
    mock_bot.send_document = AsyncMock(return_value={"message_id": 42})

    res = await send_telegram_file(
        bot=mock_bot,
        chat_id=12345,
        file_path=test_file,
        caption="A" * 2000,  # Описание больше 1024 символов
        allow_unsafe_path=True,
    )

    assert res == {"message_id": 42}
    assert mock_bot.send_document.called
    kwargs = mock_bot.send_document.call_args.kwargs
    assert len(kwargs["caption"]) == 1024  # smart_truncate лимит


@pytest.mark.asyncio
async def test_send_telegram_file_directory_auto_zip(tmp_path: Path):
    test_dir = tmp_path / "folder_to_send"
    test_dir.mkdir()
    (test_dir / "data.txt").write_text("hello", encoding="utf-8")

    mock_bot = MagicMock()
    mock_bot.send_document = AsyncMock(return_value={"message_id": 99})

    res = await send_telegram_file(
        bot=mock_bot,
        chat_id=12345,
        file_path=test_dir,
        allow_unsafe_path=True,
    )

    assert res == {"message_id": 99}
    assert mock_bot.send_document.called


@pytest.mark.asyncio
async def test_send_telegram_file_path_traversal_shield(tmp_path: Path):
    base_dir = tmp_path / "safe_zone"
    base_dir.mkdir()

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret_data", encoding="utf-8")

    mock_bot = MagicMock()

    with pytest.raises(PathTraversalError):
        await send_telegram_file(
            bot=mock_bot,
            chat_id=12345,
            file_path=outside_file,
            allow_unsafe_path=False,
            base_dir=base_dir,
        )
