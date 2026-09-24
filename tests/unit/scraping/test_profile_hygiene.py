"""Тесты для chutils.scraping.profiles.hygiene (sanitize_profile)."""

import json
from pathlib import Path

from chutils.scraping import ProfileManager, sanitize_profile


def test_sanitize_profile_non_existent(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist"
    assert sanitize_profile(non_existent) is False


def test_sanitize_profile_resets_crash_flags_and_sessions(tmp_path: Path):
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
        },
    }
    with open(prefs_file, "w", encoding="utf-8") as f:
        json.dump(initial_prefs, f)

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
    result = sanitize_profile(profile_dir)
    assert result is True

    # Проверяем, что Preferences обновлены
    with open(prefs_file, encoding="utf-8") as f:
        updated_prefs = json.load(f)

    assert updated_prefs["profile"]["exit_type"] == "Normal"
    assert updated_prefs["profile"]["exited_cleanly"] is True
    assert updated_prefs["session"]["restore_on_startup"] == 1

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


def test_sanitize_profile_via_profile_manager(tmp_path: Path):
    profile_dir = tmp_path / "pm_profile"
    profile_dir.mkdir()
    prefs_file = profile_dir / "Preferences"
    prefs_file.write_text(json.dumps({"profile": {"exit_type": "Crashed"}}))

    res = ProfileManager.sanitize_profile(profile_dir, profile_dir_name="")
    assert res is True

    updated = json.loads(prefs_file.read_text(encoding="utf-8"))
    assert updated["profile"]["exit_type"] == "Normal"
    assert updated["profile"]["exited_cleanly"] is True
