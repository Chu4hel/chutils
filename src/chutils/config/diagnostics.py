"""
Логика формирования диагностических отчетов по конфигурации.
"""

import json
from typing import Dict, List, Any

from chutils.cli_utils import get_console
from chutils.env import is_rich_enabled

# Список ключевых слов, значения которых должны маскироваться по умолчанию
SECRET_KEYWORDS = {
    "password", "secret", "api_key", "token", "auth", "key", "pwd", "credential"
}


def mask_value(key: str, value: Any, show_secrets: bool = False) -> str:
    """
    Маскирует значение, если ключ похож на секрет.
    """
    if show_secrets:
        return str(value)

    k_lower = key.lower()
    if any(keyword in k_lower for keyword in SECRET_KEYWORDS):
        return "[MASKED]"

    return str(value)


def format_trace(trace_data: Dict[str, Dict[str, List[Dict[str, Any]]]], format_type: str = 'tree',
                 show_secrets: bool = False) -> str:
    """
    Форматирует данные трассировки в выбранный формат.
    """
    if format_type == 'json':
        return _format_json(trace_data, show_secrets)
    elif format_type == 'table':
        return _format_table(trace_data, show_secrets)
    else:
        return _format_tree(trace_data, show_secrets)


def _format_json(trace_data: Dict[str, Dict[str, List[Dict[str, Any]]]], show_secrets: bool) -> str:
    """Форматирует трассировку в JSON."""
    if not show_secrets:
        # Глубокое копирование и маскирование
        masked_data = {}
        for section, keys in trace_data.items():
            masked_data[section] = {}
            for key, history in keys.items():
                masked_data[section][key] = [
                    {"source": item["source"], "value": mask_value(key, item["value"], False)}
                    for item in history
                ]
        return json.dumps(masked_data, indent=4, ensure_ascii=False)

    return json.dumps(trace_data, indent=4, ensure_ascii=False)


def _format_table(trace_data: Dict[str, Dict[str, List[Dict[str, Any]]]], show_secrets: bool) -> str:
    """Форматирует трассировку в таблицу (Rich или текст)."""
    use_rich = is_rich_enabled()
    console = get_console()

    if use_rich:
        from rich.table import Table
        table = Table(title="Трассировка конфигурации (Diagnostics)", show_lines=True)
        table.add_column("Секция", style="cyan")
        table.add_column("Ключ", style="green")
        table.add_column("Итоговое значение", style="bold yellow")
        table.add_column("История источников (Победитель внизу)", style="dim")

        for section in sorted(trace_data.keys()):
            for key in sorted(trace_data[section].keys()):
                history = trace_data[section][key]
                final_val = mask_value(key, history[-1]["value"], show_secrets)

                history_lines = []
                for item in history:
                    val = mask_value(key, item["value"], show_secrets)
                    history_lines.append(f"• {item['source']}: {val}")

                table.add_row(section, key, final_val, "\n".join(history_lines))

        with console.capture() as capture:
            console.print(table)
        return capture.get()
    else:
        lines = ["=== Трассировка конфигурации ===", ""]
        for section in sorted(trace_data.keys()):
            for key in sorted(trace_data[section].keys()):
                history = trace_data[section][key]
                final_val = mask_value(key, history[-1]["value"], show_secrets)
                lines.append(f"[{section}] {key} = {final_val}")
                for item in history:
                    val = mask_value(key, item["value"], show_secrets)
                    lines.append(f"  <- {item['source']}: {val}")
                lines.append("")
        return "\n".join(lines)


def _format_tree(trace_data: Dict[str, Dict[str, List[Dict[str, Any]]]], show_secrets: bool) -> str:
    """Форматирует трассировку в дерево (Rich или текст)."""
    use_rich = is_rich_enabled()
    console = get_console()

    if use_rich:
        from rich.tree import Tree
        root = Tree("📁 [bold blue]Configuration Root[/bold blue]")

        for section in sorted(trace_data.keys()):
            sec_tree = root.add(f"📂 [cyan]{section}[/cyan]")
            for key in sorted(trace_data[section].keys()):
                history = trace_data[section][key]
                final_val = mask_value(key, history[-1]["value"], show_secrets)
                winner_source = history[-1]["source"]

                key_node = sec_tree.add(
                    f"[green]{key}[/green] = [yellow]{final_val}[/yellow] ([dim]{winner_source}[/dim])")

                if len(history) > 1:
                    for item in history[:-1]:
                        val = mask_value(key, item["value"], show_secrets)
                        key_node.add(f"[dim]Перекрыто из {item['source']}: {val}[/dim]")

        with console.capture() as capture:
            console.print(root)
        return capture.get()
    else:
        return _format_table(trace_data, show_secrets)  # Fallback to text list/table
