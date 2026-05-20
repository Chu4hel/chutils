from unittest.mock import MagicMock

from chutils.cli_utils import FallbackConsole, get_console


def test_fallback_console_print(capsys):
    console = FallbackConsole()
    # Должен игнорировать style и другие именованные аргументы Rich
    console.print("Hello", style="bold", justify="center", markup=True)
    captured = capsys.readouterr()
    assert captured.out == "Hello\n"


def test_fallback_console_rule(capsys):
    console = FallbackConsole()
    console.rule("Title")
    captured = capsys.readouterr()
    assert "--- Title ---" in captured.out


def test_get_console_fallback_when_rich_unavailable(monkeypatch):
    from chutils import cli_utils
    monkeypatch.setattr(cli_utils, "RICH_AVAILABLE", False)
    monkeypatch.setattr(cli_utils, "_console", None)

    console = get_console()
    assert isinstance(console, FallbackConsole)


def test_get_console_fallback_when_no_color(monkeypatch, mocker):
    from chutils import cli_utils
    monkeypatch.setattr(cli_utils, "RICH_AVAILABLE", True)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(cli_utils, "_console", None)

    console = get_console()
    assert isinstance(console, FallbackConsole)


def test_get_console_returns_rich_when_available(monkeypatch, mocker):
    from chutils import cli_utils

    # Мокаем Console, чтобы не зависеть от реальной установки rich
    mock_console_class = mocker.patch("chutils.cli_utils.Console", create=True)
    mock_console_instance = MagicMock()
    mock_console_class.return_value = mock_console_instance

    monkeypatch.setattr(cli_utils, "RICH_AVAILABLE", True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("CH_NO_COLOR", raising=False)
    monkeypatch.setattr(cli_utils, "_console", None)

    console = get_console()
    assert console == mock_console_instance
