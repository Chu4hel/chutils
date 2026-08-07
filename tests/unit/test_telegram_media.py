"""Unit-тесты для download_user_file и защиты Path Traversal."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from chutils.exceptions import ChutilsException, PathTraversalError
from chutils.telegram.media import download_user_file


@pytest.mark.asyncio
async def test_download_user_file_mock_bot(tmp_path: Path):
    target_dir = tmp_path / "downloads"

    # Мок aiogram Bot объекта
    mock_bot = MagicMock()
    mock_file = MagicMock()
    mock_file.file_path = "photos/file_0.jpg"
    mock_file.file_size = 500
    mock_bot.get_file = AsyncMock(return_value=mock_file)

    # Имитируем запись файла при вызове download_file
    async def mock_download(file_path, destination):
        Path(destination).write_bytes(b"fake_image_bytes")

    mock_bot.download_file = AsyncMock(side_effect=mock_download)

    saved_path = await download_user_file(
        bot=mock_bot,
        file_id="tg_file_123",
        target_dir=target_dir,
        custom_filename="user_photo.jpg",
    )

    assert saved_path.exists()
    assert saved_path.name == "user_photo.jpg"
    assert saved_path.read_bytes() == b"fake_image_bytes"


@pytest.mark.asyncio
async def test_download_user_file_path_traversal_shield(tmp_path: Path):
    target_dir = tmp_path / "downloads"

    mock_bot = MagicMock()
    mock_file = MagicMock()
    mock_file.file_path = "documents/file_1.pdf"
    mock_bot.get_file = AsyncMock(return_value=mock_file)
    mock_bot.download_file = AsyncMock()

    # Опасное имя файла с выходом из папки ../../../etc/passwd
    dangerous_filename = "../../../etc/passwd"

    saved_path = await download_user_file(
        bot=mock_bot,
        file_id="tg_file_456",
        target_dir=target_dir,
        custom_filename=dangerous_filename,
        allow_unsafe_path=False,
    )

    # Защита safe_filename должна обезвредить опасные символы
    assert saved_path.parent.resolve() == target_dir.resolve()
    assert ".." not in saved_path.name


@pytest.mark.asyncio
async def test_download_user_file_max_size_exceeded(tmp_path: Path):
    target_dir = tmp_path / "downloads"

    mock_bot = MagicMock()
    mock_file = MagicMock()
    mock_file.file_path = "video/huge.mp4"
    mock_file.file_size = 100 * 1024 * 1024  # 100 MB
    mock_bot.get_file = AsyncMock(return_value=mock_file)

    with pytest.raises(ChutilsException, match="превышает допустимый лимит"):
        await download_user_file(
            bot=mock_bot,
            file_id="huge_video_id",
            target_dir=target_dir,
            max_size_bytes=10 * 1024 * 1024,  # Лимит 10 MB
        )
