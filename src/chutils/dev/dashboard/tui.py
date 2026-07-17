"""
Основной модуль TUI-интерфейса дашборда CLI-команд.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from rich.align import Align
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from chutils.dev.dashboard.indexer import CLICommandDiscoverer, CLICommandInfo
from chutils.dev.dashboard.input import InputReader

if TYPE_CHECKING:
    from rich.console import Console


class DashboardTUI:
    """Контроллер интерактивного TUI-дашборда."""

    console: Console

    def __init__(self, console: Console) -> None:
        """Инициализирует дашборд.

        Args:
            console: Экземпляр консоли rich.
        """
        self.console = console
        self.root_dir = Path.cwd()
        self.discoverer = CLICommandDiscoverer(self.root_dir)
        self.commands: list[CLICommandInfo] = []
        self.filtered_commands: list[CLICommandInfo] = []

        # Навигация и состояние
        self.mode: Literal["list", "search", "form", "running"] = "list"
        self.selected_cmd_idx = 0
        self.search_query = ""

        # Состояние формы ввода
        self.form_fields: dict[str, str] = {}  # {имя_аргумента: значение}
        self.form_focus_idx = 0  # Индекс сфокусированного поля в форме

        # Буфер логов выполнения
        self.log_lines: list[str] = []
        self.process_runner: subprocess.Popen[str] | None = None
        self.log_thread_running = False

        # Кэш истории параметров
        self.history_path = self.root_dir / ".chutils_dashboard_history.json"
        self.history: dict[str, dict[str, str]] = self._load_history()

    def run(self) -> None:
        """Запускает основной цикл TUI-дашборда."""
        # Сбор команд
        self.commands = self.discoverer.discover()
        self.filtered_commands = list(self.commands)

        # Переводим терминал в альтернативный экран, чтобы не портить историю консоли
        with self.console.screen():
            # Скрываем курсор
            self.console.show_cursor(False)

            layout = self._create_layout()

            with InputReader() as reader:
                with Live(layout, console=self.console, refresh_per_second=10, screen=True) as live:
                    while True:
                        # Если процесс запущен, вычитываем логи
                        if self.mode == "running":
                            self._update_logs()

                        key = reader.get_key()
                        if key:
                            if key == "ctrl-c":
                                self._terminate_running_process()
                                break

                            # Обработка клавиш в зависимости от режима
                            if self.mode == "list":
                                if not self._handle_list_keys(key):
                                    break
                            elif self.mode == "search":
                                self._handle_search_key(key)
                            elif self.mode == "form":
                                self._handle_form_key(key)
                            elif self.mode == "running":
                                self._handle_running_key(key)

                        # Обновляем макет
                        self._refresh_layout(layout)
                        live.update(layout)

                        time.sleep(0.01)

            # Восстанавливаем курсор при выходе
            self.console.show_cursor(True)

    def _create_layout(self) -> Layout:
        """Создает начальный макет TUI.

        Returns:
            Экземпляр Layout.
        """
        layout = Layout()
        layout.split_column(
            Layout(name="main", ratio=12),
            Layout(name="footer", size=1),
        )
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=2),
        )
        layout["right"].split_column(
            Layout(name="top", ratio=1),
            Layout(name="bottom", ratio=1),
        )
        return layout

    def _refresh_layout(self, layout: Layout) -> None:
        """Обновляет содержимое панелей макета на основе текущего состояния.

        Args:
            layout: Текущий макет.
        """
        layout["left"].update(self._render_left_panel())
        layout["right"]["top"].update(self._render_top_right_panel())
        layout["right"]["bottom"].update(self._render_bottom_right_panel())
        layout["footer"].update(self._render_footer())

    # --- Рендеринг панелей ---

    def _render_left_panel(self) -> Panel:
        """Отрисовывает левую панель со списком команд."""
        title = " CLI-команды проекта "
        if self.mode == "search":
            title = " [Поиск] CLI-команды проекта "

        content = Text()

        # Поле поиска
        search_style = "bold yellow" if self.mode == "search" else "dim"
        content.append("🔍 Поиск: ", style="bold")
        content.append(f"{self.search_query}\n", style=search_style)
        content.append("─" * 30 + "\n", style="dim")

        if not self.filtered_commands:
            content.append("\n  Команды не найдены", style="dim italic")
        else:
            for idx, cmd in enumerate(self.filtered_commands):
                is_selected = (idx == self.selected_cmd_idx)

                # Стилизация выбранного элемента
                if is_selected:
                    if self.mode == "form":
                        prefix = "  "
                        style = "bold white"
                    else:
                        prefix = " > "
                        style = "bold green"
                else:
                    prefix = "  "
                    style = "white"

                content.append(f"{prefix}{cmd.name}\n", style=style)

        # Рамка зеленая, если активен список
        border_style = "bold green" if self.mode in ("list", "search") else "dim"
        return Panel(content, title=title, border_style=border_style)

    def _render_top_right_panel(self) -> Panel:
        """Отрисовывает верхнюю правую панель (карточка или форма)."""
        if not self.filtered_commands:
            return Panel(Text("Выберите команду слева", style="dim"), title=" Справка / Форма запуска ")

        cmd = self.filtered_commands[self.selected_cmd_idx]

        if self.mode == "form":
            return self._render_form_panel(cmd)

        # Режим отображения справки (LIST)
        content = Text()
        content.append("Команда: ", style="bold")
        content.append(f"{cmd.name}\n", style="bold cyan")
        content.append("Файл: ", style="bold")
        content.append(f"{cmd.file_path}\n\n", style="dim")

        content.append("Описание:\n", style="bold yellow")
        doc = cmd.docstring or "Нет описания."
        # Убираем Args секцию из основного описания для красоты
        main_doc = doc.split("Args:")[0].strip()
        content.append(f"{main_doc}\n\n")

        content.append("Параметры:\n", style="bold yellow")
        if not cmd.arguments:
            content.append("  Нет параметров\n", style="dim")
        else:
            for arg in cmd.arguments:
                def_str = f" = {arg.default_str}" if arg.default_str is not None else ""
                help_str = f" — {arg.help_text}" if arg.help_text else ""
                content.append(f"  • {arg.name}", style="bold green")
                content.append(f" ({arg.type_str}){def_str}", style="cyan")
                content.append(f"{help_str}\n")

        return Panel(content, title=" Карточка команды ", border_style="dim")

    def _render_form_panel(self, cmd: CLICommandInfo) -> Panel:
        """Отрисовывает форму ввода аргументов."""
        content = Text()
        content.append("Запуск команды: ", style="bold")
        content.append(f"{cmd.name}\n", style="bold cyan")
        content.append("Заполните аргументы функции:\n\n", style="dim")

        for idx, arg in enumerate(cmd.arguments):
            is_focused = (idx == self.form_focus_idx)
            focus_prefix = "> " if is_focused else "  "
            focus_style = "bold yellow" if is_focused else "white"

            val = self.form_fields.get(arg.name, "")

            # Рендерим поле ввода
            content.append(focus_prefix, style=focus_style)
            content.append(f"{arg.name}", style=focus_style)
            content.append(f" ({arg.type_str}): ", style="cyan")

            # Подсвечиваем значение
            if arg.type_str == "bool":
                display_val = f"[ {val} ]"
            else:
                display_val = f"\"{val}\"" if val else "[ пусто ]"

            content.append(display_val, style="bold green" if val else "dim red")

            # Выводим описание аргумента
            if arg.help_text:
                content.append(f"  # {arg.help_text}", style="dim italic")
            content.append("\n")

        content.append("\n")

        # Кнопка Запуск
        run_focused = (self.form_focus_idx == len(cmd.arguments))
        run_style = "bold black on green" if run_focused else "bold green"
        content.append("   [ ЗАПУСТИТЬ КОМАНДУ ]   ", style=run_style)

        # Кнопка Назад
        back_focused = (self.form_focus_idx == len(cmd.arguments) + 1)
        back_style = "bold black on red" if back_focused else "bold red"
        content.append("   [ НАЗАД ]   \n", style=back_style)

        return Panel(content, title=" Ввод параметров ", border_style="bold yellow")

    def _render_bottom_right_panel(self) -> Panel:
        """Отрисовывает нижнюю панель логов выполнения."""
        border_style = "bold red" if self.mode == "running" else "dim"
        title = " Лог выполнения команды "
        if self.mode == "running":
            title = " [ВЫПОЛНЕНИЕ] Лог выполнения команды "

        if not self.log_lines:
            return Panel(
                Align.center(Text("Логи отсутствуют. Запустите команду из формы.", style="dim")),
                title=title,
                border_style=border_style,
            )

        # Выводим последние 20 строк логов для автопрокрутки
        content = Text()
        for line in self.log_lines[-20:]:
            content.append(line)

        return Panel(content, title=title, border_style=border_style)

    def _render_footer(self) -> Text:
        """Отрисовывает нижнюю строку с подсказками по клавишам."""
        footer = Text()
        if self.mode == "list":
            footer.append(" [F] Поиск ", style="bold black on yellow")
            footer.append("  ")
            footer.append(" [Enter] Запуск/Форма ", style="bold black on green")
            footer.append("  ")
            footer.append(" [Esc/Ctrl+C] Выход ", style="bold black on red")
        elif self.mode == "search":
            footer.append(" [Буквы/Цифры] Ввод поискового запроса ", style="bold black on yellow")
            footer.append("  ")
            footer.append(" [Esc] Сбросить поиск ", style="bold black on red")
            footer.append("  ")
            footer.append(" [Enter] Подтвердить выбор ", style="bold black on green")
        elif self.mode == "form":
            footer.append(" [Up/Down/Tab] Навигация ", style="bold black on yellow")
            footer.append("  ")
            footer.append(" [Буквы/Цифры] Редактирование ", style="bold black on green")
            footer.append("  ")
            footer.append(" [Esc] Назад ", style="bold black on red")
        elif self.mode == "running":
            footer.append(" [Esc/Ctrl+C] Остановить выполнение и вернуться ", style="bold black on red")
        return footer

    # --- Обработка клавиатуры ---

    def _handle_list_keys(self, key: str) -> bool:
        """Обрабатывает клавиши в режиме списка."""
        if key == "escape":
            return False
        elif key == "up":
            if self.selected_cmd_idx > 0:
                self.selected_cmd_idx -= 1
        elif key == "down":
            if self.selected_cmd_idx < len(self.filtered_commands) - 1:
                self.selected_cmd_idx += 1
        elif key in ("f", "F"):
            self.mode = "search"
        elif key == "enter":
            if self.filtered_commands:
                self._enter_form_mode()
        return True

    def _handle_search_key(self, key: str) -> None:
        """Обрабатывает клавиши в режиме поиска."""
        if key == "escape":
            self.search_query = ""
            self.filtered_commands = list(self.commands)
            self.selected_cmd_idx = 0
            self.mode = "list"
        elif key == "backspace":
            self.search_query = self.search_query[:-1]
            self._filter_commands()
        elif key == "enter":
            self.mode = "list"
        elif len(key) == 1:
            self.search_query += key
            self._filter_commands()

    def _handle_form_key(self, key: str) -> None:
        """Обрабатывает клавиши в режиме формы."""
        cmd = self.filtered_commands[self.selected_cmd_idx]
        total_fields = len(cmd.arguments) + 2  # аргументы + 2 кнопки

        if key == "escape":
            self.mode = "list"
            return

        # Навигация по полям
        if key in ("down", "tab"):
            self.form_focus_idx = (self.form_focus_idx + 1) % total_fields
        elif key in ("up", "shift-tab"):
            self.form_focus_idx = (self.form_focus_idx - 1) % total_fields

        # Если фокус на кнопках
        elif self.form_focus_idx == len(cmd.arguments):  # Кнопка Запуск
            if key == "enter":
                self._run_command_process(cmd)
        elif self.form_focus_idx == len(cmd.arguments) + 1:  # Кнопка Назад
            if key == "enter":
                self.mode = "list"

        # Если фокус на аргументе
        else:
            arg = cmd.arguments[self.form_focus_idx]

            # Для bool переключаем
            if arg.type_str == "bool":
                if key in ("left", "right", " ", "enter"):
                    current_val = self.form_fields.get(arg.name, "False")
                    new_val = "False" if current_val == "True" else "True"
                    self.form_fields[arg.name] = new_val

            # Для остальных - текстовый ввод
            else:
                if key == "backspace":
                    current_val = self.form_fields.get(arg.name, "")
                    self.form_fields[arg.name] = current_val[:-1]
                elif key == "enter":
                    # Перемещаемся на следующее поле
                    self.form_focus_idx = (self.form_focus_idx + 1) % total_fields
                elif len(key) == 1:
                    # Добавляем символ в поле ввода
                    self.form_fields[arg.name] = self.form_fields.get(arg.name, "") + key

    def _handle_running_key(self, key: str) -> None:
        """Обрабатывает клавиши в режиме выполнения."""
        if key in ("escape", "ctrl-c"):
            self._terminate_running_process()
            self.mode = "form"

    # --- Вспомогательные методы бизнес-логики ---

    def _filter_commands(self) -> None:
        """Фильтрует список команд на основе поискового запроса."""
        query = self.search_query.lower()
        self.filtered_commands = [
            c for c in self.commands if query in c.name.lower() or (c.docstring and query in c.docstring.lower())
        ]
        self.selected_cmd_idx = 0

    def _enter_form_mode(self) -> None:
        """Инициализирует поля формы при входе."""
        cmd = self.filtered_commands[self.selected_cmd_idx]
        self.form_fields = {}
        self.form_focus_idx = 0

        # Загружаем из истории или подставляем значения по умолчанию
        cmd_history = self.history.get(cmd.name, {})

        for arg in cmd.arguments:
            if arg.name in cmd_history:
                self.form_fields[arg.name] = cmd_history[arg.name]
            elif arg.default_str is not None:
                # В AST дефолты приходят в виде строк (например, "True", "1.0", "'value'")
                # Очищаем кавычки для удобства ввода
                val = arg.default_str
                if val.startswith(("'", '"')) and val.endswith(("'", '"')):
                    val = val[1:-1]
                self.form_fields[arg.name] = val
            else:
                # Если дефолта нет
                if arg.type_str == "bool":
                    self.form_fields[arg.name] = "False"
                else:
                    self.form_fields[arg.name] = ""

        self.mode = "form"

    def _run_command_process(self, cmd: CLICommandInfo) -> None:
        """Запускает процесс выполнения CLI-команды.

        Args:
            cmd: Выбранная CLI-команда.
        """
        # Сохраняем в историю
        self._save_to_history(cmd.name, self.form_fields)

        self.log_lines = [f"[bold green]>>> Запуск {cmd.name} из {cmd.file_path}...[/bold green]\n"]
        self.mode = "running"

        # Строим аргументы командной строки
        args_list: list[str] = []
        for arg in cmd.arguments:
            val = self.form_fields.get(arg.name, "").strip()

            # Для bool флагов
            if arg.type_str == "bool":
                if val == "True":
                    # Преобразуем имя в --имя-аргумента
                    args_list.append(f"--{arg.name.replace('_', '-')}")

            # Для остальных позиционных или именованных аргументов
            elif val:
                # Проверим, опциональный ли он (был ли дефолт в AST)
                is_optional = (arg.default_str is not None)
                if is_optional:
                    args_list.append(f"--{arg.name.replace('_', '-')}")
                    args_list.append(val)
                else:
                    args_list.append(val)

        # Формируем shell-вызов через однострочник Python, чтобы гарантированно импортировать
        # и запустить функцию из ее исходного файла.
        py_cmd = (
            "import sys, importlib.util; "
            f"spec = importlib.util.spec_from_file_location('__main__', {repr(cmd.file_path)}); "
            "mod = importlib.util.module_from_spec(spec); "
            "sys.modules['__main__'] = mod; "
            "spec.loader.exec_module(mod); "
            f"getattr(mod, {repr(cmd.name)})()"
        )

        env = os.environ.copy()  # chutils: ignore[ChutilsIntegrationRule]
        current_paths = sys.path.copy()
        if "" not in current_paths:
            current_paths.insert(0, "")
        env["PYTHONPATH"] = os.pathsep.join(p for p in current_paths if p)

        try:
            self.process_runner = subprocess.Popen(
                [sys.executable, "-c", py_cmd] + args_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            # Переводим дескриптор в неблокирующий режим (для Unix)
            if sys.platform != "win32":
                import fcntl
                if self.process_runner.stdout:
                    fd = self.process_runner.stdout.fileno()
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        except Exception as e:
            self.log_lines.append(f"[bold red]Ошибка запуска подпроцесса: {e}[/bold red]\n")
            self.process_runner = None
            self.mode = "form"

    def _update_logs(self) -> None:
        """Читает лог вывода запущенного процесса."""
        if not self.process_runner:
            return

        # Проверяем stdout
        if self.process_runner.stdout:
            try:
                if sys.platform == "win32":
                    # На Windows читаем построчно, используя kbhit-подобную проверку
                    # Но subprocess Popen.stdout в режиме text=True буферизует вывод.
                    # Для Windows используем простой readline с проверкой завершения
                    # (чтобы избежать вечной блокировки, делаем poll() и читаем по байтам или строкам)
                    self.process_runner.stdout.flush()
                    # Проверяем, завершился ли процесс
                    self.process_runner.poll()
                    # Читаем доступные строки
                    while True:
                        line = self.process_runner.stdout.readline()
                        if not line:
                            break
                        self.log_lines.append(line)
                else:
                    # На Unix дескриптор неблокирующий, читаем пока есть данные
                    while True:
                        line = self.process_runner.stdout.readline()
                        if not line:
                            break
                        self.log_lines.append(line)
            except Exception:
                pass

        # Проверяем статус процесса
        status = self.process_runner.poll()
        if status is not None:
            # Считываем остатки логов
            if self.process_runner.stdout:
                try:
                    for line in self.process_runner.stdout:
                        self.log_lines.append(line)
                except Exception:
                    pass

            color = "green" if status == 0 else "red"
            self.log_lines.append(
                f"\n[bold {color}]>>> Процесс завершился с кодом {status}[/bold {color}]\n"
            )
            self.process_runner = None
            self.mode = "form"

    def _terminate_running_process(self) -> None:
        """Завершает выполняющийся подпроцесс."""
        if self.process_runner:
            self.log_lines.append("\n[bold red]>>> Завершение процесса пользователем...[/bold red]\n")
            try:
                self.process_runner.terminate()
                self.process_runner.wait(timeout=1.0)
            except Exception:
                try:
                    self.process_runner.kill()
                except Exception:
                    pass
            self.process_runner = None

    # --- Загрузка и сохранение истории ---

    def _load_history(self) -> dict[str, dict[str, str]]:
        """Загружает историю параметров из файла кэша."""
        from typing import cast
        if self.history_path.exists():
            try:
                with open(self.history_path, encoding="utf-8") as f:
                    return cast(dict[str, dict[str, str]], json.load(f))
            except Exception:
                return {}
        return {}

    def _save_to_history(self, cmd_name: str, fields: dict[str, str]) -> None:
        """Сохраняет параметры команды в историю и записывает в файл.

        Args:
            cmd_name: Имя команды.
            fields: Поля параметров.
        """
        self.history[cmd_name] = fields
        try:
            from chutils.fs import atomic_write
            atomic_write(self.history_path, self.history, indent=2, ensure_ascii=False)
        except Exception:
            pass
