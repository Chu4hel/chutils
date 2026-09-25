"""Тесты для сброса аварийного состояния профилей Chromium и проверки блокировок."""

from __future__ import annotations

import json
from pathlib import Path

from chutils import (
    is_profile_locked,
    sanitize_profile,
    sanitize_profile_crash_state,
)
from chutils.scraping.nodriver import (
    is_profile_locked as nodriver_is_profile_locked,
)
from chutils.scraping.nodriver import (
    sanitize_profile as nodriver_sanitize_profile,
)
from chutils.scraping.nodriver import (
    sanitize_profile_crash_state as nodriver_sanitize_crash_state,
)
from chutils.scraping.profiles import (
    is_profile_locked as profiles_is_profile_locked,
)
from chutils.scraping.profiles import (
    sanitize_profile as profiles_sanitize_profile,
)
from chutils.scraping.profiles import (
    sanitize_profile_crash_state as profiles_sanitize_crash_state,
)


def test_hygiene_exports_and_aliases() -> None:
    """Проверяет корректность экспорта и идентичность алиасов функций санитайзинга."""
    assert sanitize_profile is profiles_sanitize_profile
    assert sanitize_profile is nodriver_sanitize_profile
    assert sanitize_profile_crash_state is profiles_sanitize_crash_state
    assert sanitize_profile_crash_state is nodriver_sanitize_crash_state
    assert is_profile_locked is profiles_is_profile_locked
    assert is_profile_locked is nodriver_is_profile_locked


def test_sanitize_profile_crash_state(tmp_path: Path) -> None:
    """Проверяет сброс флагов падения в Preferences, Local State и очистку сессий."""
    profile_dir = tmp_path / "chrome_user_data"
    default_dir = profile_dir / "Default"
    default_dir.mkdir(parents=True)

    # 1. Создаем Preferences в Default с флагами падения
    prefs_default = default_dir / "Preferences"
    crashed_prefs = {
        "profile": {
            "exit_type": "Crashed",
            "exited_cleanly": False,
        },
        "session": {
            "restore_on_startup": 5,
            "restore_after_crash": True,
        },
    }
    prefs_default.write_text(json.dumps(crashed_prefs), encoding="utf-8")

    # 2. Создаем Preferences в корне профиля
    prefs_root = profile_dir / "Preferences"
    crashed_root_prefs = {
        "exit_type": "Crashed",
        "exited_cleanly": False,
    }
    prefs_root.write_text(json.dumps(crashed_root_prefs), encoding="utf-8")

    # 3. Создаем Local State с флагом перезапуска после сбоя
    local_state = profile_dir / "Local State"
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
    local_state.write_text(json.dumps(local_state_data), encoding="utf-8")

    # 4. Создаем артефакты сессий и вкладок
    sessions_dir = default_dir / "Sessions"
    sessions_dir.mkdir()
    (sessions_dir / "Session_13320000000000").write_text("dummy session data")
    (sessions_dir / "Tabs_13320000000000").write_text("dummy tabs data")
    (default_dir / "Current Session").write_text("current session")
    (default_dir / "Last Session").write_text("last session")

    # Выполняем санитайзинг через sanitize_profile_crash_state
    result = sanitize_profile_crash_state(profile_dir)
    assert result is True

    # Проверяем Default/Preferences
    updated_prefs = json.loads(prefs_default.read_text(encoding="utf-8"))
    assert updated_prefs["profile"]["exit_type"] == "Normal"
    assert updated_prefs["profile"]["exited_cleanly"] is True
    assert updated_prefs["session"]["restore_on_startup"] == 1
    assert updated_prefs["session"].get("restore_after_crash") is False

    # Проверяем root Preferences
    updated_root = json.loads(prefs_root.read_text(encoding="utf-8"))
    assert updated_root["exit_type"] == "Normal"
    assert updated_root["exited_cleanly"] is True

    # Проверяем Local State
    updated_ls = json.loads(local_state.read_text(encoding="utf-8"))
    assert updated_ls["profile"]["info_cache"]["Default"]["exit_type"] == "Normal"
    assert updated_ls["profile"]["info_cache"]["Default"]["exited_cleanly"] is True
    assert updated_ls["was"]["restarted"] is False

    # Проверяем, что артефакты сессий удалены
    assert not (sessions_dir / "Session_13320000000000").exists()
    assert not (sessions_dir / "Tabs_13320000000000").exists()
    assert not (default_dir / "Current Session").exists()
    assert not (default_dir / "Last Session").exists()


def test_sanitize_nonexistent_profile_returns_false() -> None:
    """Проверяет обработку несуществующей директории."""
    assert sanitize_profile_crash_state(Path("/nonexistent/path/for/profile")) is False


def test_is_profile_locked_detection(tmp_path: Path) -> None:
    """Проверяет обнаружение активных блокировок процесса Chromium."""
    from unittest.mock import patch

    profile_dir = tmp_path / "lock_test_profile"
    assert is_profile_locked(profile_dir) is False

    profile_dir.mkdir()
    assert is_profile_locked(profile_dir) is False

    lockfile = profile_dir / "lockfile"
    lockfile.write_text("12345")
    # Незаблокированный файл не считается заблокированным
    assert is_profile_locked(profile_dir) is False

    # Имитируем блокировку файла другим процессом
    with patch("builtins.open", side_effect=PermissionError("Файл занят другим процессом")):
        assert is_profile_locked(profile_dir) is True
