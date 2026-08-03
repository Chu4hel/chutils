"""Модуль работы со стек-моделями и хранением профилей браузеров (.chprofile)."""

import json
import zipfile
from pathlib import Path
from chutils.logger import setup_logger
from chutils.scraping.profiles.models import BrowserProfile

logger = setup_logger(__name__)


def save_profile_to_file(
    profile: BrowserProfile,
    filepath: str | Path,
    password: str | None = None,
) -> Path:
    """Сохранить модель BrowserProfile в zip-архив .chprofile.

    Args:
        profile: Экземпляр модели BrowserProfile.
        filepath: Путь к сохраняемому файлу (.chprofile).
        password: Необязательный пароль для Fernet-шифрования.

    Returns:
        Path к сохраненному файлу.
    """
    target_path = Path(filepath)
    if not target_path.name.endswith(".chprofile"):
        target_path = target_path.with_suffix(".chprofile")

    from chutils.fs import ensure_dir

    ensure_dir(target_path.parent)

    json_bytes = profile.model_dump_json(indent=2).encode("utf-8")

    if password:
        from chutils.crypto import encrypt_portable

        json_bytes = encrypt_portable(json_bytes.decode("utf-8"), password).encode("utf-8")

    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("profile.json", json_bytes)

    logger.debug("Профиль браузера успешно сохранен: %s", target_path)
    return target_path


def load_profile_from_file(
    filepath: str | Path,
    password: str | None = None,
) -> BrowserProfile:
    """Загрузить и распарсить модель BrowserProfile из архива .chprofile.

    Args:
        filepath: Путь к файлу .chprofile.
        password: Необязательный пароль расшифровки.

    Returns:
        Экземпляр BrowserProfile.
    """
    target_path = Path(filepath)
    if not target_path.exists():
        raise FileNotFoundError(f"Файл профиля не найден: {target_path}")

    with zipfile.ZipFile(target_path, "r") as zip_file:
        if "profile.json" not in zip_file.namelist():
            raise ValueError("Некорректный формат .chprofile: отсутствует profile.json")
        raw_bytes = zip_file.read("profile.json")

    content_str = raw_bytes.decode("utf-8")

    if password:
        from chutils.crypto import decrypt_portable

        decrypted = decrypt_portable(content_str, password)
        if decrypted is None:
            raise ValueError("Не удалось расшифровать профиль. Проверьте правильность пароля.")
        content_str = decrypted

    data_dict = json.loads(content_str)
    return BrowserProfile.model_validate(data_dict)
