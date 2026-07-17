import json
import time
import urllib.error
from pathlib import Path

import pytest

from chutils.dev.upgrade_client import (
    fetch_changelogs,
    get_cache_paths,
    load_releases_from_cache,
    save_releases_to_cache,
)


@pytest.fixture
def fake_base_dir(tmp_path):
    return str(tmp_path)


def test_cache_paths(fake_base_dir):
    """Проверяет правильность путей кэша."""
    cache_dir, cache_file = get_cache_paths(fake_base_dir)
    assert cache_dir == Path(fake_base_dir) / ".chutils" / "changelog_cache"
    assert cache_file == cache_dir / "github_releases.json"


def test_save_and_load_releases_from_cache(fake_base_dir):
    """Проверяет сохранение и загрузку из кэша."""
    cache_dir, cache_file = get_cache_paths(fake_base_dir)
    releases = [{"tag_name": "v3.2.0", "body": "Feature A"}]

    save_releases_to_cache(cache_dir, cache_file, releases)
    assert cache_file.exists()

    # Свежий кэш должен загрузиться
    loaded = load_releases_from_cache(cache_file)
    assert loaded == releases

    # Искусственно состарим файл кэша
    past_time = time.time() - (13 * 60 * 60)  # 13 часов назад
    import os
    os.utime(cache_file, (past_time, past_time))

    # Кэш устарел, должен вернуть None по умолчанию
    assert load_releases_from_cache(cache_file) is None

    # Должен загрузить при принудительном игнорировании времени жизни
    assert load_releases_from_cache(cache_file, ignore_lifetime=True) == releases


def test_fetch_changelogs_from_valid_cache(mocker, fake_base_dir):
    """Проверяет, что при валидном кэше сетевой запрос не совершается."""
    cache_dir, cache_file = get_cache_paths(fake_base_dir)
    releases = [{"tag_name": "v3.2.0", "body": "From cache"}]
    save_releases_to_cache(cache_dir, cache_file, releases)

    mock_urlopen = mocker.patch("urllib.request.urlopen")

    res = fetch_changelogs(fake_base_dir)
    assert res == releases
    mock_urlopen.assert_not_called()


def test_fetch_changelogs_network_success(mocker, fake_base_dir):
    """Проверяет успешное получение данных по сети."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_response = mocker.MagicMock()
    mock_response.read.return_value = b'[{"tag_name": "v3.2.0", "body": "From network"}]'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    res = fetch_changelogs(fake_base_dir)
    assert len(res) == 1
    assert res[0]["tag_name"] == "v3.2.0"
    assert res[0]["body"] == "From network"

    # Данные должны быть записаны в кэш
    _, cache_file = get_cache_paths(fake_base_dir)
    assert cache_file.exists()
    assert json.loads(cache_file.read_text(encoding="utf-8")) == res


def test_fetch_changelogs_network_failure_fallback_to_stale_cache(mocker, fake_base_dir):
    """Проверяет fallback к устаревшему кэшу при сбое сети."""
    cache_dir, cache_file = get_cache_paths(fake_base_dir)
    releases = [{"tag_name": "v3.2.0", "body": "Stale data"}]
    save_releases_to_cache(cache_dir, cache_file, releases)

    # Искусственно состарим файл
    past_time = time.time() - (13 * 60 * 60)
    import os
    os.utime(cache_file, (past_time, past_time))

    # Симулируем сетевую ошибку
    mocker.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("No network"))

    res = fetch_changelogs(fake_base_dir)
    assert res == releases  # Возвращает устаревший кэш


def test_fetch_changelogs_network_failure_no_cache(mocker, fake_base_dir):
    """Проверяет возврат пустого списка при сбое сети и отсутствии кэша."""
    mocker.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("No network"))

    res = fetch_changelogs(fake_base_dir)
    assert res == []
