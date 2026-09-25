"""Утилиты для очистки профилей браузера и сброса флагов аварийного завершения (Profile Hygiene & Crash Flags)."""

import json
import logging  # chutils: ignore[ChutilsIntegrationRule]
from pathlib import Path

from chutils.fs import atomic_write, remove_path

logger = logging.getLogger(__name__)


def sanitize_profile(
    profile_path: str | Path,
    *,
    reset_crash_flags: bool = True,
    clear_sessions: bool = True,
    profile_dir_name: str = "Default",
    restore_on_startup: int = 1,
) -> bool:
    """Очищает профиль Chromium от артефактов падений и сбрасывает флаги некорректного завершения.

    Предотвращает появление инфобара и модального диалога "Восстановить страницы? Chromium завершился некорректно",
    который искажает геометрию окна (viewport), перехватывает фокус, сдвигает координаты кликов и детектируется
    антифрод-системами как признак автоматизации.

    Args:
        profile_path: Путь к корневой директории пользовательских данных Chromium (user_data_dir)
            или непосредственно к каталогу профиля (например, Default).
        reset_crash_flags: Сбросить флаги exit_type в "Normal" и exited_cleanly в True в файле Preferences и Local State.
        clear_sessions: Очистить директории и файлы сохраненных сессий и вкладок (Default/Sessions,
            Session_*, Tabs_*).
        profile_dir_name: Имя поддиректории профиля Chromium (по умолчанию "Default").
        restore_on_startup: Значение session.restore_on_startup (1 = открывать новую вкладку).

    Returns:
        True, если очистка выполнена успешно или директория валидна; False в случае ошибки.
    """
    root = Path(profile_path).resolve()
    if not root.exists():
        logger.debug("Каталог профиля не существует: %s", root)
        return False

    # 1. Поиск всех возможных файлов Preferences
    candidate_prefs: list[Path] = []
    for pref_candidate in (
        root / profile_dir_name / "Preferences",
        root / "Default" / "Preferences",
        root / "Preferences",
    ):
        if pref_candidate.is_file() and pref_candidate not in candidate_prefs:
            candidate_prefs.append(pref_candidate)

    if reset_crash_flags:
        for prefs_file in candidate_prefs:
            try:
                data = json.loads(prefs_file.read_text(encoding="utf-8"))
                modified = False

                # Сброс флагов некорректного завершения в секции 'profile'
                if "profile" not in data or not isinstance(data["profile"], dict):
                    data["profile"] = {}
                    modified = True

                prof = data["profile"]
                if prof.get("exit_type") not in ("Normal", "none"):
                    prof["exit_type"] = "Normal"
                    modified = True
                if prof.get("exited_cleanly") is not True:
                    prof["exited_cleanly"] = True
                    modified = True

                # Верхний уровень (старые или кастомные сборки Chromium)
                if data.get("exit_type") and data.get("exit_type") not in ("Normal", "none"):
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
                if session.get("restore_after_crash") is True:
                    session["restore_after_crash"] = False
                    modified = True

                if modified:
                    json_str = json.dumps(data, ensure_ascii=False, indent=2)
                    atomic_write(prefs_file, json_str, mode="w", encoding="utf-8")
                    logger.debug("Флаги некорректного завершения сброшены в %s", prefs_file)
            except Exception as exc:
                logger.warning("Не удалось обновить Preferences профиля %s: %s", prefs_file, exc)

        # Сброс флагов падения в Local State (в корне user_data_dir)
        local_state_file = root / "Local State"
        if local_state_file.is_file():
            try:
                ls_data = json.loads(local_state_file.read_text(encoding="utf-8"))
                ls_modified = False

                # Проверка info_cache в profile
                if isinstance(ls_data.get("profile"), dict):
                    info_cache = ls_data["profile"].get("info_cache")
                    if isinstance(info_cache, dict):
                        for prof_entry in info_cache.values():
                            if isinstance(prof_entry, dict):
                                if prof_entry.get("exit_type") not in ("Normal", "none", None):
                                    prof_entry["exit_type"] = "Normal"
                                    ls_modified = True
                                if prof_entry.get("exited_cleanly") is False:
                                    prof_entry["exited_cleanly"] = True
                                    ls_modified = True

                if isinstance(ls_data.get("was"), dict) and ls_data["was"].get("restarted"):
                    ls_data["was"]["restarted"] = False
                    ls_modified = True

                if ls_modified:
                    atomic_write(
                        local_state_file,
                        json.dumps(ls_data, ensure_ascii=False, indent=2),
                        mode="w",
                        encoding="utf-8",
                    )
                    logger.debug("Флаги падений сброшены в Local State: %s", local_state_file)
            except Exception as exc:
                logger.debug("Не удалось обновить Local State профиля %s: %s", local_state_file, exc)

    # 2. Очистка артефактов сессий и вкладок
    if clear_sessions:
        session_dirs = [
            root / profile_dir_name / "Sessions",
            root / "Default" / "Sessions",
            root / "Sessions",
        ]
        seen_dirs: set[Path] = set()

        for s_dir in session_dirs:
            if s_dir.is_dir() and s_dir not in seen_dirs:
                seen_dirs.add(s_dir)
                try:
                    for file_path in s_dir.iterdir():
                        if file_path.is_file():
                            try:
                                file_path.unlink(missing_ok=True)
                            except (PermissionError, OSError) as exc:
                                logger.debug(
                                    "Файл сессии занят процессом Chromium (%s), пропуск: %s",
                                    file_path.name,
                                    exc,
                                )
                            except Exception:
                                pass
                    try:
                        s_dir.rmdir()
                    except (PermissionError, OSError):
                        pass
                    logger.debug("Очищены файлы сохраненных вкладок в %s", s_dir)
                except Exception as exc:
                    logger.debug("Не удалось очистить каталог сессий %s: %s", s_dir, exc)

        # Очистка файлов Session_* и Tabs_* в корне профиля
        target_parents = [root / profile_dir_name, root / "Default", root]
        seen_parents: set[Path] = set()
        for parent_dir in target_parents:
            if parent_dir.is_dir() and parent_dir not in seen_parents:
                seen_parents.add(parent_dir)
                for pattern in (
                    "Session_*",
                    "Tabs_*",
                    "Current Session",
                    "Current Tabs",
                    "Last Session",
                    "Last Tabs",
                ):
                    for target in parent_dir.glob(pattern):
                        try:
                            if target.is_file():
                                target.unlink(missing_ok=True)
                            elif target.is_dir():
                                remove_path(target)
                            logger.debug("Удален артефакт сессии Chromium: %s", target)
                        except (PermissionError, OSError) as exc:
                            logger.debug("Файл сессии занят процессом (%s), пропуск: %s", target.name, exc)
                        except Exception as exc:
                            logger.warning("Не удалось удалить артефакт сессии %s: %s", target, exc)

    return True


def sanitize_profile_crash_state(profile_dir: str | Path) -> bool:
    """Сбрасывает флаги аварийного закрытия Chromium, предотвращая модальное окно 'Восстановить страницы'.

    Алиас для `sanitize_profile(profile_dir, reset_crash_flags=True, clear_sessions=True)`.

    Args:
        profile_dir: Путь к директории профиля пользователя Chrome.

    Returns:
        True, если очистка выполнена успешно.
    """
    return sanitize_profile(profile_dir, reset_crash_flags=True, clear_sessions=True)


def is_profile_locked(profile_dir: str | Path) -> bool:
    """Проверяет, заблокирован ли каталог профиля другим запущенным процессом Chromium.

    Сканирует файлы блокировок Chrome: `lockfile`, `SingletonLock`
    и проверяет доступ к эксклюзивной базе `Default/Web Data`.

    Args:
        profile_dir: Путь к директории профиля Chrome.

    Returns:
        True, если каталог профиля заблокирован или используется другим процессом.
    """
    root = Path(profile_dir).resolve()
    if not root.exists():
        return False

    candidates = [
        root / "lockfile",
        root / "SingletonLock",
        root / "Default" / "lockfile",
        root / "Default" / "SingletonLock",
        root / "Default" / "Web Data",
        root / "Web Data",
    ]

    for candidate in candidates:
        if candidate.is_file():
            try:
                with open(candidate, "r+b"):
                    pass
            except (PermissionError, OSError):
                return True
    return False


__all__ = [
    "is_profile_locked",
    "sanitize_profile",
    "sanitize_profile_crash_state",
]
