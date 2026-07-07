import sys
from dataclasses import dataclass

import pytest

from chutils.cli import main


@dataclass
class CliResult:
    """Результат выполнения CLI команды."""
    exit_code: int
    stdout: str
    stderr: str


class CliRunner:
    """
    Эмулятор CliRunner для argparse.
    Предоставляет интерфейс для вызова CLI и захвата вывода.
    """

    def __init__(self, capsys, monkeypatch):
        self.capsys = capsys
        self.monkeypatch = monkeypatch

    def invoke(self, args: list[str] | None = None) -> CliResult:
        """
        Вызывает основную функцию CLI с заданными аргументами.
        """
        if args is None:
            args = []

        # Подменяем sys.argv
        self.monkeypatch.setattr(sys, "argv", ["chutils"] + list(args))

        # Принудительно отключаем цвета и markup для стабильности тестов
        self.monkeypatch.setenv("NO_COLOR", "1")
        self.monkeypatch.setenv("CH_NO_COLOR", "1")

        exit_code = 0
        try:
            # Сбрасываем кэши консолей перед каждым запуском, чтобы подхватить новые sys.stdout/stderr
            from chutils import cli_utils
            cli_utils._console = None
            cli_utils._err_console = None

            main()
        except SystemExit as e:
            if isinstance(e.code, int):
                exit_code = e.code
            else:
                exit_code = 0 if e.code is None else 1
        except Exception:
            # Если возникло необработанное исключение, оно будет поймано pytest
            raise

        captured = self.capsys.readouterr()
        return CliResult(
            exit_code=exit_code,
            stdout=captured.out,
            stderr=captured.err
        )


@pytest.fixture
def cli_runner(capsys, monkeypatch):
    """Фикстура для удобного тестирования CLI."""
    return CliRunner(capsys, monkeypatch)
