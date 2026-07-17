"""
Юнит-тесты для интерактивного TUI-дашборда CLI-команд.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast
from rich.console import Console
from unittest.mock import MagicMock

from chutils.cli_utils import get_console
from chutils.dev.dashboard.indexer import (
    CLICommandDiscoverer,
    CLICommandInfo,
    parse_docstring_args,
)
from chutils.dev.dashboard.input import InputReader
from chutils.dev.dashboard.tui import DashboardTUI


def test_parse_docstring_args() -> None:
    """Проверяет парсинг docstring для извлечения описания параметров."""
    doc = """
    Тестовая функция.

    Args:
        name (str): Имя пользователя.
        count (int): Количество повторений.
        debug (bool): Режим отладки.
    """
    args = parse_docstring_args(doc)
    assert args["name"] == "Имя пользователя."
    assert args["count"] == "Количество повторений."
    assert args["debug"] == "Режим отладки."

    # Пустой docstring
    assert parse_docstring_args(None) == {}
    assert parse_docstring_args("") == {}


def test_cli_command_discoverer(tmp_path: Path) -> None:
    """Проверяет сканирование файлов проекта и извлечение CLI-команд."""
    # Создаем тестовый файл с функцией, декорированной @cli_command
    test_file = tmp_path / "test_cmd.py"
    test_file.write_text(
        """
from chutils import cli_command

@cli_command
def my_test_func(name: str, count: int = 5, verbose: bool = False):
    \"\"\"
    Описание тестовой команды.

    Args:
        name (str): Имя.
        count (int): Счетчик.
    \"\"\"
    pass
""",
        encoding="utf-8",
    )

    discoverer = CLICommandDiscoverer(tmp_path)
    commands = discoverer.discover()

    assert len(commands) == 1
    cmd = commands[0]
    assert cmd.name == "my_test_func"
    assert "test_cmd.py" in cmd.file_path
    assert cmd.docstring is not None
    assert "Описание тестовой команды." in cmd.docstring

    # Проверка аргументов
    assert len(cmd.arguments) == 3

    arg_name = cmd.arguments[0]
    assert arg_name.name == "name"
    assert arg_name.type_str == "str"
    assert arg_name.default_str is None
    assert arg_name.help_text == "Имя."

    arg_count = cmd.arguments[1]
    assert arg_count.name == "count"
    assert arg_count.type_str == "int"
    assert arg_count.default_str == "5"

    arg_verbose = cmd.arguments[2]
    assert arg_verbose.name == "verbose"
    assert arg_verbose.type_str == "bool"
    assert arg_verbose.default_str == "False"


def test_input_reader_win(monkeypatch: Any) -> None:
    """Проверяет InputReader в режиме Windows."""
    monkeypatch.setattr(sys, "platform", "win32")

    mock_msvcrt = MagicMock()
    mock_msvcrt.kbhit.return_value = True
    mock_msvcrt.getch.side_effect = [b"a", b"\xe0", b"H", b"\x03"]

    monkeypatch.setitem(sys.modules, "msvcrt", mock_msvcrt)

    reader = InputReader()
    assert reader.is_win is True

    # Символ 'a'
    assert reader.get_key() == "a"
    # Стрелка вверх
    assert reader.get_key() == "up"
    # Ctrl+C
    assert reader.get_key() == "ctrl-c"


def test_input_reader_unix(monkeypatch: Any) -> None:
    """Проверяет InputReader в режиме Unix."""
    monkeypatch.setattr(sys, "platform", "linux")

    mock_termios = MagicMock()
    mock_tty = MagicMock()
    mock_select = MagicMock()
    mock_sys_stdin = MagicMock()

    mock_select.select.side_effect = [
        ([mock_sys_stdin], [], []),  # Первый вызов в get_key (есть данные)
        ([mock_sys_stdin], [], []),  # В get_key_unix при чтении спецсимвола
    ]
    mock_sys_stdin.read.side_effect = ["\x1b", "[", "A"]

    monkeypatch.setitem(sys.modules, "termios", mock_termios)
    monkeypatch.setitem(sys.modules, "tty", mock_tty)
    monkeypatch.setitem(sys.modules, "select", mock_select)
    monkeypatch.setattr(sys, "stdin", mock_sys_stdin)

    reader = InputReader()
    assert reader.is_win is False

    with reader:
        assert reader.get_key() == "up"


def test_tui_history_cache(tmp_path: Path) -> None:
    """Проверяет сохранение и загрузку истории параметров."""
    console = get_console()
    tui = DashboardTUI(console=cast(Console, console))
    tui.root_dir = tmp_path
    tui.history_path = tmp_path / ".chutils_dashboard_history.json"

    # История пуста
    assert tui._load_history() == {}

    # Сохраняем
    fields = {"name": "Ivan", "count": "10"}
    tui._save_to_history("test_cmd", fields)

    # Загружаем снова
    loaded = tui._load_history()
    assert loaded["test_cmd"] == fields


def test_tui_filtering_and_navigation() -> None:
    """Проверяет фильтрацию и навигацию по списку в TUI."""
    console = get_console()
    tui = DashboardTUI(console=cast(Console, console))

    # Тестовые данные команд
    cmd1 = CLICommandInfo("boosty_sync", "sync.py", "Синхронизация бусти", [])
    cmd2 = CLICommandInfo("ai_lint", "lint.py", "Анализатор ИИ", [])
    tui.commands = [cmd1, cmd2]
    tui.filtered_commands = list(tui.commands)

    # Фильтрация
    tui.search_query = "sync"
    tui._filter_commands()
    assert len(tui.filtered_commands) == 1
    assert tui.filtered_commands[0].name == "boosty_sync"

    # Сброс
    tui.search_query = ""
    tui._filter_commands()
    assert len(tui.filtered_commands) == 2


def test_tui_panels_rendering() -> None:
    """Проверяет, что рендеринг панелей не вызывает ошибок."""
    console = get_console()
    tui = DashboardTUI(console=cast(Console, console))

    # Создаем команду с аргументами (str и bool)
    from chutils.dev.dashboard.indexer import CLIArgument
    arg1 = CLIArgument("name", "str", None, "Имя")
    arg2 = CLIArgument("verbose", "bool", "True", "Логи")
    cmd = CLICommandInfo("ai_lint", "lint.py", "Анализатор ИИ", [arg1, arg2])
    tui.filtered_commands = [cmd]
    tui.selected_cmd_idx = 0

    # 1. Проверяем рендеринг в режиме списка (list)
    tui.mode = "list"
    assert tui._render_left_panel() is not None
    assert tui._render_top_right_panel() is not None
    assert tui._render_bottom_right_panel() is not None
    assert tui._render_footer() is not None

    # 2. В режиме поиска (search)
    tui.mode = "search"
    assert tui._render_left_panel() is not None
    assert tui._render_footer() is not None

    # 3. В режиме формы (form)
    tui.mode = "form"
    tui.form_fields = {"name": "val", "verbose": "True"}
    assert tui._render_top_right_panel() is not None
    assert tui._render_footer() is not None

    # Проверяем фокус на кнопке "Запустить"
    tui.form_focus_idx = 2
    assert tui._render_top_right_panel() is not None

    # Проверяем фокус на кнопке "Назад"
    tui.form_focus_idx = 3
    assert tui._render_top_right_panel() is not None

    # 4. В режиме выполнения (running)
    tui.mode = "running"
    tui.log_lines = ["line 1", "line 2"]
    assert tui._render_bottom_right_panel() is not None
    assert tui._render_footer() is not None

    # Тестируем случай пустых команд
    tui.filtered_commands = []
    assert tui._render_left_panel() is not None
    assert tui._render_top_right_panel() is not None
    assert tui._render_bottom_right_panel() is not None


def test_tui_form_navigation() -> None:
    """Проверяет логику навигации и изменения полей в режиме формы."""
    console = get_console()
    tui = DashboardTUI(console=cast(Console, console))

    from chutils.dev.dashboard.indexer import CLIArgument
    arg1 = CLIArgument("name", "str", None, "Имя")
    arg2 = CLIArgument("debug", "bool", "False", "Отладка")
    cmd = CLICommandInfo("test_cmd", "test.py", "Тест", [arg1, arg2])

    tui.filtered_commands = [cmd]
    tui.selected_cmd_idx = 0
    tui._enter_form_mode()

    assert tui.form_fields["name"] == ""
    assert tui.form_fields["debug"] == "False"
    assert tui.form_focus_idx == 0

    # Вводим текст в поле 'name'
    tui._handle_form_key("i")
    tui._handle_form_key("v")
    assert tui.form_fields["name"] == "iv"

    # Backspace
    tui._handle_form_key("backspace")
    assert tui.form_fields["name"] == "i"

    # Переходим на следующее поле (debug)
    tui._handle_form_key("down")
    assert tui.form_focus_idx == 1

    # Изменяем bool переключатель debug
    tui._handle_form_key(" ")
    assert tui.form_fields["debug"] == "True"

    # Переходим на кнопку Запуск
    tui._handle_form_key("down")
    assert tui.form_focus_idx == 2

    # Переходим на кнопку Назад
    tui._handle_form_key("down")
    assert tui.form_focus_idx == 3

    # Нажимаем enter на кнопке Назад -> возвращаемся в список
    tui._handle_form_key("enter")
    assert tui.mode == "list"


def test_tui_list_keys_handling() -> None:
    """Проверяет обработку клавиш в режиме списка."""
    console = get_console()
    tui = DashboardTUI(console=cast(Console, console))
    tui.filtered_commands = [
        CLICommandInfo("cmd1", "1.py", "descr", []),
        CLICommandInfo("cmd2", "2.py", "descr", []),
    ]
    tui.selected_cmd_idx = 0
    tui.mode = "list"

    # Скролл вниз
    tui._handle_list_keys("down")
    assert tui.selected_cmd_idx == 1

    # Скролл вверх
    tui._handle_list_keys("up")
    assert tui.selected_cmd_idx == 0

    # Вход в режим поиска
    tui._handle_list_keys("f")
    assert tui.mode == "search"  # type: ignore[comparison-overlap]

    # Выход
    assert tui._handle_list_keys("escape") is False


def test_tui_search_keys_handling() -> None:
    """Проверяет обработку клавиш в режиме поиска."""
    console = get_console()
    tui = DashboardTUI(console=cast(Console, console))
    tui.commands = [
        CLICommandInfo("sync_db", "1.py", "descr", []),
        CLICommandInfo("ai_lint", "2.py", "descr", []),
    ]
    tui.filtered_commands = list(tui.commands)
    tui.mode = "search"

    # Ввод букв
    tui._handle_search_key("s")
    tui._handle_search_key("y")
    assert tui.search_query == "sy"
    assert len(tui.filtered_commands) == 1

    # Backspace
    tui._handle_search_key("backspace")
    assert tui.search_query == "s"

    # Сброс (escape)
    tui._handle_search_key("escape")
    assert tui.search_query == ""
    assert tui.mode == "list"  # type: ignore[comparison-overlap]


def test_tui_process_execution(mocker: Any) -> None:
    """Проверяет запуск процесса и считывание логов."""
    console = get_console()
    tui = DashboardTUI(console=cast(Console, console))

    # Команда с аргументом
    arg = CLICommandInfo("run_test", "test.py", "descr", [])
    tui.filtered_commands = [arg]
    tui.selected_cmd_idx = 0
    tui.mode = "form"

    # Мокаем subprocess.Popen
    mock_popen = mocker.patch("subprocess.Popen")
    mock_process = MagicMock()
    mock_process.stdout = MagicMock()
    mock_process.stdout.readline.side_effect = ["log line 1\n", "log line 2\n", ""]
    mock_process.poll.side_effect = [None, None, 0, 0, 0]
    mock_popen.return_value = mock_process

    tui._run_command_process(arg)
    assert tui.mode == "running"  # type: ignore[comparison-overlap]
    assert tui.process_runner is not None

    # Считываем логи (проход 1)
    tui._update_logs()
    assert "log line 1" in "".join(tui.log_lines)

    # Считываем логи (проход 2, процесс завершился)
    tui._update_logs()
    assert "Процесс завершился с кодом 0" in "".join(tui.log_lines)
    assert tui.mode == "form"
    assert tui.process_runner is None


def test_tui_run_loop(mocker: Any) -> None:
    """Проверяет основной цикл run() с моками."""
    console = get_console()
    tui = DashboardTUI(console=cast(Console, console))

    # Мокаем методы
    mocker.patch.object(tui.discoverer, "discover", return_value=[])
    mocker.patch.object(tui, "_create_layout")
    mocker.patch.object(tui, "_refresh_layout")

    # Мокаем Live
    mock_live = MagicMock()
    mocker.patch("chutils.dev.dashboard.tui.Live", return_value=mock_live)

    # Мокаем InputReader, чтобы сразу вернуть 'escape' для выхода
    mock_reader = MagicMock()
    mock_reader.__enter__.return_value = mock_reader
    mock_reader.get_key.side_effect = ["escape"]
    mocker.patch("chutils.dev.dashboard.tui.InputReader", return_value=mock_reader)

    tui.run()
    assert getattr(tui.discoverer.discover, "called")
    assert mock_reader.get_key.called
