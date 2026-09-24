"""Утилиты для очистки профилей браузера и сброса флагов аварийного завершения (Profile Hygiene & Crash Flags)."""

from __future__ import annotations

import json
from pathlib import Path

from chutils.fs import atomic_write, remove_path
from chutils.logger import setup_logger

logger = setup_logger(__name__)


def sanitize_profile(
    profile_path: str | Path,
    *,
    reset_crash_flags: bool = True,
    clear_sessions: bool = True,
    profile_dir_name: str = "Default",
    restore_on_startup: int = 1,
) -> bool:
    """Очищает профиль Chromium от артефактов падений и сбрасывает флаги некорректного завершения.

    Предотвращает появление инфобара "Восстановить страницы? Chromium завершился некорректно",
    который искажает геометрию окна (viewport), сдвигает координаты кликов и детектируется
    антифрод-системами как признак автоматизации.

    Args:
        profile_path: Путь к корневой директории пользовательских данных Chromium (user_data_dir)
            или непосредственно к каталогу профиля (например, Default).
        reset_crash_flags: Сбросить флаги exit_type в "Normal" и exited_cleanly в True в файле Preferences.
        clear_sessions: Очистить директории и файлы сохраненных сессий и вкладок (Default/Sessions,
            Session_*, Tabs_*).
        profile_dir_name: Имя поддиректории профиля Chromium (по умолчанию "Default").
        restore_on_startup: Значение session.restore_on_startup (1 = открывать новую вкладку).

    Returns:
        True, если очистка выполнена успешно или директория валидна; False в случае ошибки.
    """
    root = Path(profile_path).resolve()
    if not root.exists():
        logger.debug(f"Каталог профиля не существует: {root}")
        return False

    # Определение пути к подкаталогу профиля (Default)
    default_dir = root / profile_dir_name if (root / profile_dir_name).exists() else root
    prefs_file = default_dir / "Preferences"

    # 1. Сброс флагов некорректного завершения в Preferences
    if reset_crash_flags and prefs_file.exists():
        try:
            with open(prefs_file, encoding="utf-8") as f:
                data = json.load(f)

            # Сброс флагов некорректного завершения
            # В Chromium exit_type и exited_cleanly могут находиться как в секции 'profile', так и на верхнем уровне
            if "profile" not in data or not isinstance(data["profile"], dict):
                data["profile"] = {}
                modified = True

            prof = data["profile"]
            if prof.get("exit_type") != "Normal":
                prof["exit_type"] = "Normal"
                modified = True
            if prof.get("exited_cleanly") is not True:
                prof["exited_cleanly"] = True
                modified = True

            # Верхний уровень (старые или кастомные сборки Chromium)
            if data.get("exit_type") and data.get("exit_type") != "Normal":
                data["exit_type"] = "Normal"
                modified = True
            if "exited_cleanly" in data and data.get("exited_cleanly") is not True:
                data["exited_cleanly"] = True
                modified = True

            # Сброс restore_on_startup и session флагов
            if "session" not in data or not isinstance(data["session"], dict):
                data["session"] = {}
                modified = True

            session = data["session"]
            if session.get("restore_on_startup") != restore_on_startup:
                session["restore_on_startup"] = restore_on_startup
                modified = True

            if modified:
                # Файл Preferences не имеет суффикса .json, поэтому сериализуем в строку
                json_str = json.dumps(data, ensure_ascii=False, indent=2)
                atomic_write(prefs_file, json_str, mode="w", encoding="utf-8")
                logger.debug(f"Флаги некорректного завершения сброшены в {prefs_file}")
        except Exception as exc:
            logger.warning(f"Не удалось обновить Preferences профиля {prefs_file}: {exc}")

    # 2. Очистка артефактов сессий и вкладок
    if clear_sessions:
        targets_to_clean: list[Path] = []

        # Каталог Default/Sessions
        sessions_dir = default_dir / "Sessions"
        if sessions_dir.exists():
            targets_to_clean.append(sessions_dir)

        # Файлы и маски Session_* и Tabs_*
        for pattern in ("Session_*", "Tabs_*", "Current Session", "Current Tabs", "Last Session", "Last Tabs"):
            targets_to_clean.extend(default_dir.glob(pattern))

        for target in targets_to_clean:
            try:
                if target.exists():
                    remove_path(target)
                    logger.debug(f"Удален артефакт сессии Chromium: {target}")
            except Exception as exc:
                logger.warning(f"Не удалось удалить артефакт сессии {target}: {exc}")

    return True
