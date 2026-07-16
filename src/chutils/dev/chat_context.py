"""Интерактивный AI-Ассистент сборки контекста (chat-context)."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from chutils.cli_utils import get_console
from chutils.dev.ast_indexer import Indexer

if TYPE_CHECKING:
    from chutils.dev.models import Node, ProjectExample


def extract_keywords(text: str) -> list[str]:
    """Извлекает ключевые слова из описания задачи.

    Args:
        text: Входной текст задачи.

    Returns:
        Список выделенных ключевых слов.
    """
    words = re.findall(r"\b[a-zA-Zа-яА-ЯёЁ]{3,}\b", text.lower())
    stop_words = {
        "для",
        "под",
        "над",
        "все",
        "как",
        "про",
        "или",
        "and",
        "the",
        "for",
        "with",
        "как",
        "что",
        "это",
    }
    return [w for w in words if w not in stop_words]


def score_node(node: Node, keywords: list[str]) -> float:
    """Оценивает релевантность узла (модуля/пакета) по ключевым словам.

    Args:
        node: Узел AST дерева, который нужно оценить.
        keywords: Список ключевых слов для поиска.

    Returns:
        Численная оценка релевантности (чем выше, тем релевантнее).
    """
    score = 0.0
    for kw in keywords:
        if kw in node.name.lower():
            score += 10.0
        if kw in (node.docstring or "").lower():
            score += 3.0
        if kw in node.summary.lower():
            score += 3.0

    for sym in node.symbols:
        for kw in keywords:
            if kw in sym.name.lower():
                score += 5.0
            if kw in (sym.docstring or "").lower():
                score += 2.0
            if kw in sym.summary.lower():
                score += 2.0
    return score


def get_all_leaf_modules(node: Node) -> list[tuple[str, Node]]:
    """Собирает все конечные модули (файлы) в дереве AST.

    Args:
        node: Корневой узел для обхода.

    Returns:
        Список кортежей вида (имя_модуля, узел_модуля).
    """
    modules = []
    if node.type == "module":
        modules.append((node.name, node))
    for child in node.children:
        modules.extend(get_all_leaf_modules(child))
    return modules


def filter_node_by_modules(node: Node, modules: list[str]) -> Node | None:
    """Фильтрует AST-дерево, оставляя только указанные модули.

    Args:
        node: Узел AST дерева для фильтрации.
        modules: Список имен разрешенных модулей.

    Returns:
        Отфильтрованный узел или None, если модуль не подходит.
    """
    node_name_lower = node.name.lower()
    node_path_lower = node.path.replace("\\", "/").lower()

    # Проверяем точное или частичное совпадение имени модуля/пути
    is_matched = any(
        mod.lower() in node_name_lower or mod.lower() in node_path_lower
        for mod in modules
    )

    filtered_children = []
    for child in node.children:
        child_filtered = filter_node_by_modules(child, modules)
        if child_filtered is not None:
            filtered_children.append(child_filtered)

    if is_matched:
        return node
    elif filtered_children:
        new_node = node.model_copy()
        new_node.children = filtered_children
        new_node.symbols = []
        return new_node
    return None


def filter_symbols_by_layer(node: Node, allowed_layers: set[str]) -> Node:
    """Фильтрует символы по слою абстракции.

    Args:
        node: Узел AST дерева для фильтрации символов.
        allowed_layers: Множество допустимых слоев.

    Returns:
        Новый узел AST дерева с отфильтрованными символами.
    """
    new_node = node.model_copy()
    new_node.symbols = [sym for sym in node.symbols if sym.layer in allowed_layers]
    new_node.children = [
        filter_symbols_by_layer(child, allowed_layers) for child in node.children
    ]
    return new_node


def filter_examples(
        examples: list[ProjectExample],
        selected_modules: list[str] | None,
        keywords: list[str] | None,
) -> list[ProjectExample]:
    """Фильтрует few-shot примеры по выбранным модулям или ключевым словам.

    Args:
        examples: Полный список примеров.
        selected_modules: Список выбранных модулей.
        keywords: Список ключевых слов.

    Returns:
        Список релевантных примеров.
    """
    relevant_examples = []
    for ex in examples:
        is_relevant = False
        ex_text = (ex.name + " " + ex.description).lower()

        if selected_modules:
            for mod in selected_modules:
                if mod.lower() in ex_text or ex_text in mod.lower():
                    is_relevant = True
                    break

        if not is_relevant and keywords:
            for kw in keywords:
                if (
                        kw in ex_text
                        or kw in ex.good_pattern.lower()
                        or kw in ex.bad_pattern.lower()
                ):
                    is_relevant = True
                    break

        if is_relevant:
            relevant_examples.append(ex)
    return relevant_examples


def generate_tree_markdown(node: Node, indent: str = "") -> str:
    """Форматирует AST-дерево в Markdown.

    Args:
        node: Узел AST дерева для форматирования.
        indent: Начальный отступ строки.

    Returns:
        Markdown-строка с представлением дерева.
    """
    lines = []
    icon = "📁 " if node.type == "package" else "📄 "
    summary_part = f" - {node.summary}" if node.summary else ""
    lines.append(f"{indent}{icon}{node.name} ({node.layer}){summary_part}")
    for sym in node.symbols:
        sym_icon = "🔹 " if sym.type == "class" else "🔸 "
        summary_part = f" - {sym.summary}" if sym.summary else ""
        lines.append(
            f"{indent}  {sym_icon}{sym.name} ({sym.type}, {sym.layer}){summary_part}"
        )
    for child in node.children:
        lines.append(generate_tree_markdown(child, indent + "  "))
    return "\n".join(lines)


def generate_symbols_details(node: Node) -> str:
    """Форматирует сигнатуры и docstrings в Markdown.

    Args:
        node: Узел AST дерева.

    Returns:
        Markdown-строка с деталями о символах (сигнатуры, docstrings).
    """
    sections = []
    if node.symbols:
        sections.append(f"### Модуль `{node.path}`\n")
        for sym in node.symbols:
            sections.append(f"#### `{sym.type}` `{sym.name}` ({sym.layer})")
            if sym.signature:
                sections.append(f"```python\n{sym.signature}\n```")
            if sym.docstring:
                sections.append(f"{sym.docstring}\n")
            if sym.children:
                sections.append("##### Методы класса:")
                for child in sym.children:
                    summary = f" - *{child.summary}*" if child.summary else ""
                    sections.append(
                        f"- **`{child.name}`**`{child.signature or ''}` ({child.layer}){summary}"
                    )
                    if child.docstring:
                        indented_doc = "\n".join(
                            "  " + line for line in child.docstring.splitlines()
                        )
                        sections.append(f"  ```\n{indented_doc}\n  ```")
            sections.append("---")
    for child_node in node.children:
        child_details = generate_symbols_details(child_node)
        if child_details:
            sections.append(child_details)
    return "\n\n".join(sections)


def generate_examples_markdown(examples: list[ProjectExample]) -> str:
    """Форматирует few-shot примеры в Markdown.

    Args:
        examples: Список примеров для форматирования.

    Returns:
        Markdown-строка с оформленными примерами.
    """
    lines = []
    if examples:
        lines.append("## Few-Shot Примеры (Кейсы использования)\n")
        for ex in examples:
            lines.append(f"### Пример: {ex.name}")
            lines.append(f"{ex.description}\n")
            lines.append("#### ❌ Как НЕ надо делать:")
            lines.append(f"```python\n{ex.bad_pattern}\n```\n")
            lines.append("#### ✅ Как НАДО делать:")
            lines.append(f"```python\n{ex.good_pattern}\n```\n")
            lines.append("---")
    return "\n".join(lines)


def collect_context_slice(
        project_path: Path,
        modules: list[str] | None = None,
        task: str | None = None,
        layer: str = "public",
) -> str:
    """Собирает контекстный срез по заданным параметрам.

    Args:
        project_path: Путь к корню проекта.
        modules: Список выбранных модулей.
        task: Описание задачи.
        layer: Слой абстракции для фильтрации символов.

    Returns:
        Сгенерированный Markdown с контекстом.
    """
    # 1. Индексируем проект
    indexer = Indexer(str(project_path))
    index = indexer.index(include_examples=True)

    # 2. Определяем слои
    layers_hierarchy = {
        "public": {"public"},
        "internal": {"public", "internal"},
        "infrastructure": {"public", "internal", "infrastructure"},
        "private": {"public", "internal", "infrastructure", "private"},
        "all": {"public", "internal", "infrastructure", "private", "all"},
    }
    allowed_layers = layers_hierarchy.get(layer.lower(), {"public"})

    # 3. Фильтруем по задаче/теме (автоматический отбор модулей)
    keywords: list[str] = []
    selected_modules = list(modules) if modules else []

    if task and not selected_modules:
        keywords = extract_keywords(task)
        if keywords:
            all_leaves = get_all_leaf_modules(index.root)
            scored_modules = []
            for name, leaf_node in all_leaves:
                score = score_node(leaf_node, keywords)
                if score > 0:
                    scored_modules.append((score, name))

            # Сортируем по релевантности
            scored_modules.sort(key=lambda x: x[0], reverse=True)
            selected_modules = [name for _, name in scored_modules]

    # 4. Фильтруем AST-дерево
    filtered_root = index.root
    if selected_modules:
        filtered_res = filter_node_by_modules(index.root, selected_modules)
        if filtered_res is not None:
            filtered_root = filtered_res
        else:
            pass

    # 5. Фильтруем символы по слою абстракции
    filtered_root = filter_symbols_by_layer(filtered_root, allowed_layers)

    # 6. Фильтруем примеры
    examples = filter_examples(
        index.examples, selected_modules or None, keywords or None
    )

    # 7. Форматируем Markdown
    markdown_parts = []
    markdown_parts.append("# Контекстный срез для ИИ-ассистента")
    markdown_parts.append(
        f"Сгенерирован: {time.strftime('%Y-%m-%d %H:%M:%S')} | Слой абстракции: `{layer}`\n"
    )

    if task:
        markdown_parts.append(f"**Описание задачи:** {task}\n")
    if selected_modules:
        markdown_parts.append(f"**Выбранные модули:** {', '.join(selected_modules)}\n")

    markdown_parts.append("## AST-структура выбранных подсистем")
    markdown_parts.append("```")
    markdown_parts.append(generate_tree_markdown(filtered_root))
    markdown_parts.append("```\n")

    details = generate_symbols_details(filtered_root)
    if details:
        markdown_parts.append("## Подробное описание API")
        markdown_parts.append(details)
        markdown_parts.append("")

    examples_md = generate_examples_markdown(examples)
    if examples_md:
        markdown_parts.append(examples_md)

    return "\n".join(markdown_parts)


def run_interactive_menu(project_path: Path) -> list[str]:
    """Запускает красивое интерактивное CLI-меню для выбора модулей.

    Args:
        project_path: Путь к корню проекта.

    Returns:
        Список выбранных пользователем модулей.
    """
    console = get_console()
    console.print(
        "[bold cyan]=== Интерактивный помощник сборки контекста ===[/bold cyan]\n"
    )

    indexer = Indexer(str(project_path))
    index = indexer.index(include_examples=False)
    all_leaves = get_all_leaf_modules(index.root)

    if not all_leaves:
        console.print("[bold red]Модули не найдены.[/bold red]")
        return []

    console.print("[bold]Доступные модули:[/bold]")
    for idx, (name, node) in enumerate(all_leaves, 1):
        summary_str = f" — [dim]{node.summary}[/dim]" if node.summary else ""
        console.print(f"  [[bold green]{idx}[/bold green]] {name}{summary_str}")

    console.print(
        "\nВведите номера нужных модулей через запятую (например, [bold]1, 3[/bold]), "
        "или введите ключевое слово для поиска:"
    )

    try:
        user_input = input("> ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Операция отменена.[/yellow]")
        return []

    if not user_input:
        console.print("[yellow]Выбор пуст.[/yellow]")
        return []

    if re.match(r"^[\d\s,]+$", user_input):
        selected_indexes = [
            int(part.strip())
            for part in user_input.split(",")
            if part.strip().isdigit()
        ]
        selected_modules = []
        for index_val in selected_indexes:
            if 1 <= index_val <= len(all_leaves):
                selected_modules.append(all_leaves[index_val - 1][0])
        return selected_modules
    else:
        keywords = extract_keywords(user_input)
        scored_modules = []
        for name, leaf_node in all_leaves:
            score = score_node(leaf_node, keywords)
            if score > 0:
                scored_modules.append((score, name))

        scored_modules.sort(key=lambda x: x[0], reverse=True)
        found = [name for _, name in scored_modules]
        if found:
            console.print(
                f"[green]По вашему запросу автоматически выбраны модули:[/green] {', '.join(found)}"
            )
            return found
        else:
            console.print(
                f"[yellow]Модули по запросу '{user_input}' не найдены.[/yellow]"
            )
            return []
