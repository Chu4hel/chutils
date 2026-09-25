"""Тесты для chutils.scraping.profiles.hygiene (sanitize_profile, sanitize_profile_crash_state, is_profile_locked)."""

from __future__ import annotations

import json
from pathlib import Path

from pytest_mock import MockerFixture

from chutils import (
    is_profile_locked,
    sanitize_profile,
    sanitize_profile_crash_state,
)
from chutils.scraping import ProfileManager, nodriver, profiles


def test_hygiene_exports_and_aliases() -> None:
    """Проверяет корректность экспорта и идентичность алиасов функций санитайзинга."""
    assert sanitize_profile is profiles.sanitize_profile
    assert sanitize_profile is nodriver.sanitize_profile
    assert sanitize_profile_crash_state is profiles.sanitize_profile_crash_state
    assert sanitize_profile_crash_state is nodriver.sanitize_profile_crash_state
    assert is_profile_locked is profiles.is_profile_locked
    assert is_profile_locked is nodriver.is_profile_locked


def test_sanitize_profile_non_existent(tmp_path: Path) -> None:
    """Проверяет обработку несуществующей директории профиля."""
    non_existent = tmp_path / "does_not_exist"
    assert sanitize_profile(non_existent) is False
    assert sanitize_profile_crash_state(non_existent) is False


def test_sanitize_profile_resets_crash_flags_and_sessions(tmp_path: Path) -> None:
    """Проверяет сброс флагов аварии в Preferences, Local State и удаление папок сессий."""
    profile_dir = tmp_path / "chrome_user_data"
    default_dir = profile_dir / "Default"
    default_dir.mkdir(parents=True)

    # Создаем Preferences с флагами аварийного завершения
    prefs_file = default_dir / "Preferences"
    initial_prefs = {
        "profile": {
            "exit_type": "Crashed",
            "exited_cleanly": False,
        },
        "session": {
            "restore_on_startup": 4,
            "restore_after_crash": True,
        },
    }
    with open(prefs_file, "w", encoding="utf-8") as f:
        json.dump(initial_prefs, f)

    # Создаем Local State с флагом падения и перезапуска
    local_state_file = profile_dir / "Local State"
    local_state_data = {
        "profile": {
            "info_cache": {
                "Default": {
                    "exit_type": "Crashed",
                    "exited_cleanly": False,
                }
            }
        },
        "was": {
            "restarted": True,
        },
    }
    local_state_file.write_text(json.dumps(local_state_data), encoding="utf-8")

    # Создаем папки и файлы сессий
    sessions_dir = default_dir / "Sessions"
    sessions_dir.mkdir()
    (sessions_dir / "Session_12345").write_text("session data")
    (sessions_dir / "Tabs_12345").write_text("tabs data")

    (default_dir / "Session_old").write_text("old session")
    (default_dir / "Tabs_old").write_text("old tabs")
    (default_dir / "Current Session").write_text("current session")
    (default_dir / "Current Tabs").write_text("current tabs")
    (default_dir / "Last Session").write_text("last session")
    (default_dir / "Last Tabs").write_text("last tabs")

    # Файл, который НЕ должен быть удален (например, куки или история)
    (default_dir / "History").write_text("history data")

    # Вызываем санитайзинг
    result = sanitize_profile_crash_state(profile_dir)
    assert result is True

    # Проверяем, что Preferences обновлены
    with open(prefs_file, encoding="utf-8") as f:
        updated_prefs = json.load(f)

    assert updated_prefs["profile"]["exit_type"] == "Normal"
    assert updated_prefs["profile"]["exited_cleanly"] is True
    assert updated_prefs["session"]["restore_on_startup"] == 1
    assert updated_prefs["session"]["restore_after_crash"] is False

    # Проверяем, что Local State очищен от маркеров падения
    updated_local_state = json.loads(local_state_file.read_text(encoding="utf-8"))
    assert updated_local_state["profile"]["info_cache"]["Default"]["exit_type"] == "Normal"
    assert updated_local_state["was"]["restarted"] is False

    # Проверяем, что артефакты сессий удалены
    assert not sessions_dir.exists()
    assert not (default_dir / "Session_old").exists()
    assert not (default_dir / "Tabs_old").exists()
    assert not (default_dir / "Current Session").exists()
    assert not (default_dir / "Current Tabs").exists()
    assert not (default_dir / "Last Session").exists()
    assert not (default_dir / "Last Tabs").exists()

    # Обычные файлы остались нетронутыми
    assert (default_dir / "History").exists()


def test_sanitize_profile_via_profile_manager(tmp_path: Path) -> None:
    """Проверяет сброс флагов через ProfileManager."""
    profile_dir = tmp_path / "pm_profile"
    profile_dir.mkdir()
    prefs_file = profile_dir / "Preferences"
    prefs_file.write_text(json.dumps({"profile": {"exit_type": "Crashed"}}))

    res = ProfileManager.sanitize_profile(profile_dir, profile_dir_name="")
    assert res is True

    updated = json.loads(prefs_file.read_text(encoding="utf-8"))
    assert updated["profile"]["exit_type"] == "Normal"
    assert updated["profile"]["exited_cleanly"] is True


def test_is_profile_locked(tmp_path: Path, mocker: MockerFixture) -> None:
    """Проверяет детекцию блокировок профиля процессами Chromium."""
    profile_dir = tmp_path / "test_locked_profile"
    assert is_profile_locked(profile_dir) is False

    profile_dir.mkdir()
    assert is_profile_locked(profile_dir) is False

    lock_file = profile_dir / "lockfile"
    lock_file.write_text("1")
    # Без удержания блокировки процессом
    assert is_profile_locked(profile_dir) is False

    # При удержании процесса другим инстансом Chromium (PermissionError/OSError)
    mocker.patch("builtins.open", side_effect=PermissionError("Locked by another process"))
    assert is_profile_locked(profile_dir) is True
