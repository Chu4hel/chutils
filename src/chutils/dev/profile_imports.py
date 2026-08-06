"""
Модуль для профилирования импортов и анализа времени холодного старта.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from chutils.cli_utils import ConsoleLike

# Импорт опциональных зависимостей rich с безопасным fallback
try:
    from rich.table import Table
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    Table = None  # type: ignore
    Tree = None  # type: ignore
    RICH_AVAILABLE = False

# Список тяжелых библиотек, импорт которых на верхнем уровне нежелателен
HEAVY_LIBRARIES = {
    "pydantic",
    "watchdog",
    "rich",
    "keyring",
    "yaml",
    "dotenv",
    "boto3",
    "google.cloud.secretmanager",
    "httpx",
    "requests",
    "urllib3",
    "psycopg2",
    "asyncpg",
    "sqlalchemy",
}
"""Список тяжелых библиотек."""


class ImportNode:
    """Узел дерева импортов."""

    def __init__(
            self,
            name: str,
            self_time_ms: float,
            cumulative_time_ms: float,
            depth: int,
    ) -> None:
        """Инициализирует узел дерева импортов.

        Args:
            name: Имя модуля.
            self_time_ms: Собственное время импорта в миллисекундах.
            cumulative_time_ms: Накопительное время импорта в миллисекундах.
            depth: Глубина вложенности.
        """
        self.name = name
        self.self_time_ms = self_time_ms
        self.cumulative_time_ms = cumulative_time_ms
        self.depth = depth
        self.children: list[ImportNode] = []

    def to_dict(self) -> dict[str, Any]:
        """Преобразует узел и его потомков в словарь для сериализации.

        Returns:
            Словарь с данными узла.
        """
        return {
            "name": self.name,
            "self_time_ms": round(self.self_time_ms, 3),
            "cumulative_time_ms": round(self.cumulative_time_ms, 3),
            "depth": self.depth,
            "children": [child.to_dict() for child in self.children],
        }


def parse_importtime_line(line: str) -> ImportNode | None:
    """Парсит одну строку вывода -X importtime.

    Args:
        line: Строка вывода.

    Returns:
        Объект ImportNode или None, если строка не соответствует формату.
    """
    # Пример: import time:      115 |          115 |   _frozen_importlib_external
    parts = line.split("|")
    if len(parts) < 3 or not parts[0].startswith("import time:"):
        return None

    try:
        self_us = int(parts[0].replace("import time:", "").strip())
        cumulative_us = int(parts[1].strip())
    except ValueError:
        return None

    indent_and_name = parts[2]
    # CPython выводит ровно один пробел после '|' перед отступами
    if indent_and_name.startswith(" "):
        indent_and_name = indent_and_name[1:]

    name = indent_and_name.lstrip()
    num_spaces = len(indent_and_name) - len(name)
    depth = num_spaces // 2

    return ImportNode(
        name=name,
        self_time_ms=self_us / 1000.0,
        cumulative_time_ms=cumulative_us / 1000.0,
        depth=depth,
    )


def build_tree(flat_imports: list[ImportNode]) -> list[ImportNode]:
    """Восстанавливает иерархическое дерево импортов из плоского списка.

    Args:
        flat_imports: Список узлов в порядке вывода CPython.

    Returns:
        Список корневых узлов дерева импортов.
    """
    roots: list[ImportNode] = []
    stack: list[ImportNode] = []

    for node in reversed(flat_imports):
        while stack and stack[-1].depth >= node.depth:
            stack.pop()

        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)

        stack.append(node)

    # Восстанавливаем оригинальный порядок следования детей и корней
    roots.reverse()
    for node in flat_imports:
        node.children.reverse()

    return roots


def profile_imports(
        target: str,
        threshold_ms: float,
        as_table: bool,
        as_json: bool,
        console: ConsoleLike,
) -> None:
    """Выполняет профилирование импортов для указанной цели.

    Args:
        target: Имя модуля или путь к файлу для импорта.
        threshold_ms: Порог времени в миллисекундах для фильтрации мелких импортов.
        as_table: Вывести результаты в виде плоской таблицы.
        as_json: Вывести результаты в формате JSON.
        console: Консоль rich для вывода.

    Raises:
        RuntimeError: Если запуск подпроцесса завершился с ошибкой.
    """
    env = os.environ.copy()  # chutils: ignore[ChutilsIntegrationRule]
    current_paths = sys.path.copy()
    if "" not in current_paths:
        current_paths.insert(0, "")
    env["PYTHONPATH"] = os.pathsep.join(p for p in current_paths if p)

    # Запуск подпроцесса с флагом -X importtime
    cmd = [sys.executable, "-X", "importtime", "-c", f"import {target}"]
    process = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    if process.returncode != 0:
        raise RuntimeError(
            f"Не удалось импортировать модуль '{target}' (exit code {process.returncode}).\n"
            f"Ошибка:\n{process.stderr}"
        )

    # Парсинг вывода
    flat_imports: list[ImportNode] = []
    for line in process.stderr.splitlines():
        node = parse_importtime_line(line)
        if node:
            flat_imports.append(node)

    if not flat_imports:
        raise RuntimeError(
            "Не удалось распарсить вывод importtime. Убедитесь, что используется стандартный интерпретатор CPython."
        )

    roots = build_tree(flat_imports)

    # Вывод результатов
    if as_json:
        result_json = {
            "target": target,
            "total_imports": len(flat_imports),
            "total_time_ms": round(sum(r.cumulative_time_ms for r in roots), 3),
            "tree": [r.to_dict() for r in roots],
        }
        print(json.dumps(result_json, indent=2, ensure_ascii=False))
        return

    # Подготовка аналитики
    total_time_ms = sum(r.cumulative_time_ms for r in roots)

    # 1. Поиск дубликатов
    import_counts: dict[str, int] = {}
    for node in flat_imports:
        import_counts[node.name] = import_counts.get(node.name, 0) + 1
    duplicates = {name: count for name, count in import_counts.items() if count > 1}

    # 2. Поиск тяжелых не-ленивых импортов на верхнем уровне (depth <= 2)
    heavy_imports: list[tuple[str, float, int]] = []
    for node in flat_imports:
        # Проверяем, относится ли имя модуля к тяжелым библиотекам (или начинается с их имени)
        base_name = node.name.split(".")[0]
        if base_name in HEAVY_LIBRARIES and node.depth <= 2:
            heavy_imports.append((node.name, node.cumulative_time_ms, node.depth))

    # Выводим форматированные данные
    if as_table:
        _render_table(flat_imports, threshold_ms, console)
    else:
        _render_tree(roots, threshold_ms, console)

    # Вывод статистики и предупреждений
    console.print()
    console.print(f"[bold]Статистика холодного старта для '{target}':[/bold]")
    console.print(f"  • Всего импортировано модулей: [cyan]{len(flat_imports)}[/cyan]")
    console.print(f"  • Общее время старта: [green]{total_time_ms:.2f}[/green] мс")

    if duplicates:
        console.print("\n[bold yellow]⚠ Обнаружены дублирующиеся импорты (утечки):[/bold yellow]")
        for name, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:5]:
            console.print(f"  • [yellow]{name}[/yellow]: повторено [cyan]{count}[/cyan] раз(а)")
        if len(duplicates) > 5:
            console.print(f"  ... и еще [cyan]{len(duplicates) - 5}[/cyan] дубликатов.")

    if heavy_imports:
        console.print("\n[bold red]⚠ Обнаружены тяжелые не-ленивые импорты на верхнем уровне:[/bold red]")
        for name, time_ms, depth in sorted(heavy_imports, key=lambda x: x[1], reverse=True):
            console.print(
                f"  • [red]{name}[/red] (глубина: {depth}) — [bold red]{time_ms:.2f}[/bold red] мс"
            )
        console.print(
            "\n[dim]Совет: Перенесите импорт этих библиотек внутрь функций/методов (Lazy Import), "
            "чтобы ускорить старт приложения.[/dim]"
        )


def _render_tree(roots: list[ImportNode], threshold_ms: float, console: ConsoleLike) -> None:
    """Отрисовывает иерархическое дерево импортов в консоли.

    Args:
        roots: Корневые узлы дерева импортов.
        threshold_ms: Минимальное время импорта для отображения.
        console: Консоль rich.
    """
    if RICH_AVAILABLE and Tree is not None:
        rich_tree = Tree("[bold]Дерево импортов модулей[/bold]")

        def add_node(rich_parent: Any, node: ImportNode) -> None:
            if node.cumulative_time_ms < threshold_ms:
                return

            if node.cumulative_time_ms > 10.0:
                time_style = "bold red"
            elif node.cumulative_time_ms > 3.0:
                time_style = "yellow"
            else:
                time_style = "green"

            label = f"{node.name} (self: [cyan]{node.self_time_ms:.2f}[/cyan] мс, cumulative: [{time_style}]{node.cumulative_time_ms:.2f}[/{time_style}] мс)"
            rich_node = rich_parent.add(label)

            for child in node.children:
                add_node(rich_node, child)

        for r in roots:
            add_node(rich_tree, r)

        console.print(rich_tree)
    else:
        print("Дерево импортов модулей:")

        def print_node(node: ImportNode) -> None:
            if node.cumulative_time_ms < threshold_ms:
                return
            indent = "  " * node.depth
            print(
                f"{indent}• {node.name} (self: {node.self_time_ms:.2f} ms, cumulative: {node.cumulative_time_ms:.2f} ms)")
            for child in node.children:
                print_node(child)

        for r in roots:
            print_node(r)


def _render_table(flat_imports: list[ImportNode], threshold_ms: float, console: ConsoleLike) -> None:
    """Отрисовывает плоскую таблицу импортов в консоли.

    Args:
        flat_imports: Плоский список импортированных узлов.
        threshold_ms: Минимальное время импорта для отображения.
        console: Консоль rich.
    """
    # Сортируем плоский список по self_time по убыванию
    sorted_imports = sorted(flat_imports, key=lambda x: x.self_time_ms, reverse=True)

    if RICH_AVAILABLE and Table is not None:
        table = Table(
            title="Тяжелые импорты (сортировка по собственному времени)",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Модуль", style="cyan")
        table.add_column("Глубина", justify="center", style="blue")
        table.add_column("Собственное время (мс)", justify="right", style="green")
        table.add_column("Накопительное время (мс)", justify="right", style="yellow")

        for node in sorted_imports:
            if node.self_time_ms < threshold_ms:
                continue
            table.add_row(
                node.name,
                str(node.depth),
                f"{node.self_time_ms:.2f}",
                f"{node.cumulative_time_ms:.2f}",
            )

        console.print(table)
    else:
        print("\nТяжелые импорты (сортировка по собственному времени):")
        print(f"{'Модуль':<50} | {'Глубина':<7} | {'Self (ms)':<10} | {'Cumulative (ms)':<15}")
        print("-" * 90)
        for node in sorted_imports:
            if node.self_time_ms < threshold_ms:
                continue
            print(f"{node.name:<50} | {node.depth:<7} | {node.self_time_ms:<10.2f} | {node.cumulative_time_ms:<15.2f}")
