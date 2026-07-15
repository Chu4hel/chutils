from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock

from chutils.commands.pypi import (
    PyPiCommand,
    find_best_mirror,
    get_current_index_url,
    measure_mirror,
    normalize_mirror_url,
    normalize_url,
)


def test_pypi_command_parsing(monkeypatch, cli_runner):
    """Проверяет корректность парсинга аргументов команды pypi."""
    mock_handle_check = MagicMock()
    monkeypatch.setattr(PyPiCommand, "handle_check", mock_handle_check)

    # 1. Запуск без параметров (должен вызвать check с дефолтами)
    result = cli_runner.invoke(["pypi"])
    assert result.exit_code == 0
    mock_handle_check.assert_called_once()

    args = mock_handle_check.call_args[0][0]
    assert args.subcommand is None or args.subcommand == "check"
    assert args.mirrors is None
    assert args.json is False
    assert args.package == "six"

    mock_handle_check.reset_mock()

    # 2. Запуск с флагами
    result = cli_runner.invoke([
        "pypi", "check",
        "-m", "https://mirror1.com,https://mirror2.com",
        "--json",
        "--package", "requests"
    ])
    assert result.exit_code == 0
    mock_handle_check.assert_called_once()

    args = mock_handle_check.call_args[0][0]
    assert args.subcommand == "check"
    assert args.mirrors == "https://mirror1.com,https://mirror2.com"
    assert args.json is True
    assert args.package == "requests"


def test_pypi_command_help_unknown(cli_runner):
    """Проверяет вызов помощи для неизвестной подкоманды."""
    result = cli_runner.invoke(["pypi", "unknown_subcommand"])
    # Должна выводиться помощь по команде pypi в stderr
    assert "subcommand" in result.stderr or "invalid choice" in result.stderr


def test_normalize_mirror_url():
    """Проверяет нормализацию URL зеркал."""
    assert normalize_mirror_url("https://pypi.org/simple") == "https://pypi.org/simple/"
    assert normalize_mirror_url("https://pypi.org/simple/ ") == "https://pypi.org/simple/"


def test_normalize_url():
    """Проверяет формирование URL для проверки пакета."""
    assert normalize_url("https://pypi.org/simple", "six") == "https://pypi.org/simple/six/"
    assert normalize_url("https://pypi.org/simple/", "six") == "https://pypi.org/simple/six/"


def test_get_current_index_url_env(monkeypatch):
    """Проверяет получение index-url через переменную окружения."""
    monkeypatch.setenv("PIP_INDEX_URL", "https://custom.pypi.org/simple/")
    assert get_current_index_url() == "https://custom.pypi.org/simple/"


def test_get_current_index_url_subprocess(monkeypatch):
    """Проверяет получение index-url через вызов pip config."""
    monkeypatch.delenv("PIP_INDEX_URL", raising=False)

    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "https://sub.pypi.org/simple/\n"
    monkeypatch.setattr("subprocess.run", mock_run)

    assert get_current_index_url() == "https://sub.pypi.org/simple/"


def test_get_current_index_url_subprocess_empty(monkeypatch):
    """Проверяет получение index-url, когда pip config возвращает пустую строку."""
    monkeypatch.delenv("PIP_INDEX_URL", raising=False)

    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""
    monkeypatch.setattr("subprocess.run", mock_run)

    assert get_current_index_url() == "https://pypi.org/simple/"


def test_get_current_index_url_fallback(monkeypatch, tmp_path):
    """Проверяет фолбек на парсинг файлов конфигурации pip."""
    monkeypatch.delenv("PIP_INDEX_URL", raising=False)

    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    monkeypatch.setattr("subprocess.run", mock_run)

    # Имитируем AppData для Windows
    fake_pip_dir = tmp_path / "pip"
    fake_pip_dir.mkdir(parents=True, exist_ok=True)
    fake_ini = fake_pip_dir / "pip.ini"
    fake_ini.write_text("[global]\nindex-url = https://ini.pypi.org/simple/\n")

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert get_current_index_url() == "https://ini.pypi.org/simple/"


def test_get_current_index_url_fallback_userprofile(monkeypatch, tmp_path):
    """Проверяет фолбек по пути USERPROFILE на Windows."""
    monkeypatch.delenv("PIP_INDEX_URL", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)

    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    monkeypatch.setattr("subprocess.run", mock_run)

    fake_pip_dir = tmp_path / "pip"
    fake_pip_dir.mkdir(parents=True, exist_ok=True)
    fake_ini = fake_pip_dir / "pip.ini"
    fake_ini.write_text("[install]\nindex-url = https://user.pypi.org/simple/\n")

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    assert get_current_index_url() == "https://user.pypi.org/simple/"


def test_get_current_index_url_fallback_invalid_ini(monkeypatch, tmp_path):
    """Проверяет фолбек, когда pip.ini поврежден и вызывает ошибку парсинга."""
    monkeypatch.delenv("PIP_INDEX_URL", raising=False)
    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    monkeypatch.setattr("subprocess.run", mock_run)

    fake_pip_dir = tmp_path / "pip"
    fake_pip_dir.mkdir(parents=True, exist_ok=True)
    fake_ini = fake_pip_dir / "pip.ini"
    # Повторяющийся ключ в одной секции вызывает DuplicateOptionError в ConfigParser
    fake_ini.write_text("[global]\nindex-url = 1\nindex-url = 2\n")

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert get_current_index_url() == "https://pypi.org/simple/"


def test_measure_mirror_success(mocker):
    """Проверяет успешное измерение характеристик зеркала."""
    mock_response_index = MagicMock()
    mock_response_index.read.return_value = b'<a href="six-1.16.0-py2.py3-none-any.whl">six-1.16.0-py2.py3-none-any.whl</a>'
    mock_response_index.__enter__.return_value = mock_response_index

    mock_response_file = MagicMock()
    mock_response_file.read.side_effect = [b"a" * 8192, b""]
    mock_response_file.__enter__.return_value = mock_response_file

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = [mock_response_index, mock_response_file]

    res = measure_mirror("https://pypi.org/simple/", "six")
    assert res["available"] is True
    assert res["latency_ms"] is not None
    assert res["download_speed_kbs"] is not None
    assert res["checked_file_url"] == "https://pypi.org/simple/six/six-1.16.0-py2.py3-none-any.whl"


def test_measure_mirror_fallback_to_first_url(mocker):
    """Проверяет фолбек на первую ссылку, если стандартные расширения не найдены."""
    mock_response_index = MagicMock()
    mock_response_index.read.return_value = b'<a href="some-nonstandard-file">Name</a>'
    mock_response_index.__enter__.return_value = mock_response_index

    mock_response_file = MagicMock()
    mock_response_file.read.side_effect = [b"data", b""]
    mock_response_file.__enter__.return_value = mock_response_file

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = [mock_response_index, mock_response_file]

    res = measure_mirror("https://pypi.org/simple/", "six")
    assert res["available"] is True
    assert res["checked_file_url"] == "https://pypi.org/simple/six/some-nonstandard-file"


def test_measure_mirror_no_links(mocker):
    """Проверяет поведение, если в индексе нет ссылок."""
    mock_response_index = MagicMock()
    mock_response_index.read.return_value = b'<html>No links here</html>'
    mock_response_index.__enter__.return_value = mock_response_index

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = [mock_response_index]

    res = measure_mirror("https://pypi.org/simple/", "six")
    assert res["available"] is True
    assert res["checked_file_url"] is None
    assert "Не найдены ссылки" in res["error"]


def test_measure_mirror_download_exception(mocker):
    """Проверяет обработку ошибок в процессе скачивания файла."""
    mock_response_index = MagicMock()
    mock_response_index.read.return_value = b'<a href="six-1.16.0.whl">six-1.16.0.whl</a>'
    mock_response_index.__enter__.return_value = mock_response_index

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    # Первый вызов успешен, второй вызывает ошибку при подключении для скачивания файла
    mock_urlopen.side_effect = [mock_response_index, ConnectionResetError("Connection reset")]

    res = measure_mirror("https://pypi.org/simple/", "six")
    assert res["available"] is True
    assert "Ошибка скачивания" in res["error"]


def test_measure_mirror_network_error(mocker):
    """Проверяет поведение при ошибке сети."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = urllib.error.URLError("DNS resolution failed")

    res = measure_mirror("https://pypi.org/simple/", "six")
    assert res["available"] is False
    assert "Ошибка сети" in res["error"]


def test_measure_mirror_http_error(mocker):
    """Проверяет поведение при ошибке HTTP."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = urllib.error.HTTPError("https://url", 404, "Not Found", {}, None)

    res = measure_mirror("https://pypi.org/simple/", "six")
    assert res["available"] is False
    assert "HTTP 404" in res["error"]


def test_measure_mirror_timeout(mocker):
    """Проверяет поведение при таймауте."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = TimeoutError()

    res = measure_mirror("https://pypi.org/simple/", "six")
    assert res["available"] is False
    assert "Таймаут" in res["error"]


def test_measure_mirror_general_exception(mocker):
    """Проверяет поведение при общей ошибке."""
    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = RuntimeError("Unknown error")

    res = measure_mirror("https://pypi.org/simple/", "six")
    assert res["available"] is False
    assert "Ошибка: Unknown error" in res["error"]


def test_find_best_mirror():
    """Проверяет алгоритм выбора наилучшего зеркала."""
    current = "https://pypi.org/simple/"

    # 1. Рекомендация не нужна, если текущее зеркало и так лучшее
    results = [
        {"url": "https://pypi.org/simple/", "available": True, "latency_ms": 50, "download_speed_kbs": 1000},
        {"url": "https://mirror1.com/simple/", "available": True, "latency_ms": 100, "download_speed_kbs": 500},
    ]
    assert find_best_mirror(results, current) is None

    # 2. Рекомендуем зеркало, если оно значительно быстрее (скорость больше на 50%+)
    results = [
        {"url": "https://pypi.org/simple/", "available": True, "latency_ms": 50, "download_speed_kbs": 1000},
        {"url": "https://mirror1.com/simple/", "available": True, "latency_ms": 30, "download_speed_kbs": 1600},
    ]
    assert find_best_mirror(results, current) == "https://mirror1.com/simple/"

    # 3. Рекомендация не выдается при незначительной разнице в скорости
    results = [
        {"url": "https://pypi.org/simple/", "available": True, "latency_ms": 50, "download_speed_kbs": 1000},
        {"url": "https://mirror1.com/simple/", "available": True, "latency_ms": 45, "download_speed_kbs": 1100},
    ]
    assert find_best_mirror(results, current) is None

    # 4. Рекомендуем по latency, если скорость не замерялась/одинаковая, но пинг лучше на 30%+ и разницу >= 50ms
    results = [
        {"url": "https://pypi.org/simple/", "available": True, "latency_ms": 200, "download_speed_kbs": 100},
        {"url": "https://mirror1.com/simple/", "available": True, "latency_ms": 100, "download_speed_kbs": 100},
    ]
    assert find_best_mirror(results, current) == "https://mirror1.com/simple/"

    # 5. Рекомендуем любое доступное, если текущее недоступно (даже если текущее не представлено в результатах)
    results = [
        {"url": "https://mirror1.com/simple/", "available": True, "latency_ms": 150, "download_speed_kbs": 200},
    ]
    assert find_best_mirror(results, current) == "https://mirror1.com/simple/"

    # 6. Рекомендуем, если у текущего скорость 0, а у лучшего больше 0
    results = [
        {"url": "https://pypi.org/simple/", "available": True, "latency_ms": 20, "download_speed_kbs": 0},
        {"url": "https://mirror1.com/simple/", "available": True, "latency_ms": 150, "download_speed_kbs": 150},
    ]
    assert find_best_mirror(results, current) == "https://mirror1.com/simple/"


def test_cli_pypi_check_output_json(cli_runner, mocker):
    """Проверяет вывод команды chutils pypi check в формате JSON."""
    mocker.patch("chutils.commands.pypi.get_current_index_url", return_value="https://pypi.org/simple/")

    mock_measure = mocker.patch("chutils.commands.pypi.measure_mirror")
    mock_measure.return_value = {
        "url": "https://pypi.org/simple/",
        "available": True,
        "latency_ms": 45.2,
        "download_speed_kbs": 2048.5,
        "error": None,
        "checked_file_url": "https://pypi.org/simple/six/six-1.16.0.whl",
    }

    mocker.patch("chutils.commands.pypi.DEFAULT_MIRRORS", ["https://pypi.org/simple/"])

    result = cli_runner.invoke(["pypi", "check", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert "current_index_url" in data
    assert "recommended_index_url" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["url"] == "https://pypi.org/simple/"
    assert data["results"][0]["download_speed_kbs"] == 2048.5


def test_cli_pypi_check_output_table(cli_runner, mocker):
    """Проверяет интерактивный вывод в виде таблицы."""
    mocker.patch("chutils.commands.pypi.get_current_index_url", return_value="https://pypi.org/simple/")

    mock_measure = mocker.patch("chutils.commands.pypi.measure_mirror")
    mock_measure.return_value = {
        "url": "https://pypi.org/simple/",
        "available": True,
        "latency_ms": 45.2,
        "download_speed_kbs": 2048.5,
        "error": None,
        "checked_file_url": "https://pypi.org/simple/six/six-1.16.0.whl",
    }
    mocker.patch("chutils.commands.pypi.DEFAULT_MIRRORS", ["https://pypi.org/simple/"])

    # 1. С включенным rich (патчим в правильном модуле namespace)
    mocker.patch("chutils.commands.pypi.is_rich_enabled", return_value=True)
    mocker.patch("chutils.cli_utils.is_rich_enabled", return_value=True)
    result = cli_runner.invoke(["pypi", "check"])
    assert result.exit_code == 0
    assert "Результаты проверки зеркал PyPI" in result.stdout
    assert "Доступен" in result.stdout
    assert "2048.5" in result.stdout

    # 2. С выключенным rich (текстовый фолбек)
    mocker.patch("chutils.commands.pypi.is_rich_enabled", return_value=False)
    result = cli_runner.invoke(["pypi", "check"])
    assert result.exit_code == 0
    assert "Результаты проверки зеркал PyPI" in result.stdout
    assert "Доступен" in result.stdout


def test_cli_pypi_check_with_custom_mirrors_and_recommendation(cli_runner, mocker):
    """Проверяет работу команды с кастомными зеркалами и выводом рекомендаций."""
    mocker.patch("chutils.commands.pypi.get_current_index_url", return_value="https://pypi.org/simple/")

    def mock_measure_fn(url, package):
        if "custom-fast" in url:
            return {
                "url": url,
                "available": True,
                "latency_ms": 10.0,
                "download_speed_kbs": 5000.0,
                "error": None,
                "checked_file_url": "https://custom-fast.org/file.whl"
            }
        else:
            return {
                "url": url,
                "available": True,
                "latency_ms": 100.0,
                "download_speed_kbs": 100.0,
                "error": None,
                "checked_file_url": "https://pypi.org/file.whl"
            }

    mocker.patch("chutils.commands.pypi.measure_mirror", side_effect=mock_measure_fn)
    mocker.patch("chutils.commands.pypi.DEFAULT_MIRRORS", ["https://pypi.org/simple/"])
    mocker.patch("chutils.commands.pypi.is_rich_enabled", return_value=False)

    result = cli_runner.invoke(["pypi", "check", "-m", "https://custom-fast.org/simple/"])
    assert result.exit_code == 0
    assert "Рекомендация:" in result.stdout
    assert "https://custom-fast.org/simple/" in result.stdout
    assert "pip config set global.index-url" in result.stdout


def test_cli_pypi_check_no_recommendation(cli_runner, mocker):
    """Проверяет вывод рекомендаций, когда текущее зеркало оптимально."""
    mocker.patch("chutils.commands.pypi.get_current_index_url", return_value="https://pypi.org/simple/")

    mock_measure = mocker.patch("chutils.commands.pypi.measure_mirror")
    mock_measure.return_value = {
        "url": "https://pypi.org/simple/",
        "available": True,
        "latency_ms": 10.0,
        "download_speed_kbs": 1000.0,
        "error": None,
        "checked_file_url": "https://pypi.org/file.whl"
    }
    mocker.patch("chutils.commands.pypi.DEFAULT_MIRRORS", ["https://pypi.org/simple/"])
    mocker.patch("chutils.commands.pypi.is_rich_enabled", return_value=False)

    result = cli_runner.invoke(["pypi", "check"])
    assert result.exit_code == 0
    assert "Ваше текущее зеркало является оптимальным" in result.stdout
