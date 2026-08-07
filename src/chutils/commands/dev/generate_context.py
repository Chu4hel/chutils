from __future__ import annotations

import argparse
import inspect
import json
import re
from pathlib import Path
from typing import Any

import chutils
from .base import SubCommand

_VOLATILE_FIELDS: tuple[str, ...] = ("git_commit", "generated_at", "project_hash")
"""Поля метаданных, которые меняются при каждой генерации."""


class GenerateContextSubCommand(SubCommand):
    """
    Подкоманда для генерации карты публичного API или иерархического индекса проекта.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду generate-context в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        gen_parser = subparsers.add_parser(
            "generate-context",
            help="Сгенерировать карту публичного API (экспорты)",
            description="Сканирует chutils и создает отчет о доступных функциях, классах и декораторах.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev generate-context -o api_map.md
  chutils dev generate-context --tree -o project_index.json
  chutils dev generate-context -f json --no-weights
""",
        )
        gen_parser.add_argument(
            "-f",
            "--format",
            choices=["markdown", "json"],
            default="markdown",
            help="Формат выходных данных (по умолчанию: markdown)",
        )
        gen_parser.add_argument(
            "-o",
            "--output",
            help="Путь к файлу для сохранения (если не указан, выводит в консоль)",
        )
        gen_parser.add_argument(
            "--tree",
            action="store_true",
            help="Генерировать иерархический семантический индекс (JSON дерево)",
        )
        gen_parser.add_argument(
            "--no-weights",
            action="store_true",
            help="Не включать веса зависимостей в графе (только для --tree)",
        )
        gen_parser.add_argument(
            "--include-examples",
            action="store_true",
            help="Включить few-shot примеры (из docs/ai_examples/) в итоговый отчет",
        )
        gen_parser.add_argument(
            "--project",
            nargs="?",
            const=".",
            default=None,
            help="Путь к целевому проекту для сканирования (если не указан, сканируется сама библиотека chutils)",
        )
        gen_parser.add_argument(
            "--ignore",
            action="append",
            help=(
                "Паттерны путей или файлов для игнорирования при сканировании (например, 'tests/*' или '*.tmp'). "
                "Можно указывать несколько раз или через запятую. Дополняет .gitignore и .chutilsignore."
            ),
        )
        gen_parser.add_argument(
            "--gitignore",
            action="store_true",
            default=True,
            help="Учитывать правила .gitignore при сканировании файлов проекта (по умолчанию включено)",
        )
        gen_parser.add_argument(
            "--no-gitignore",
            action="store_false",
            dest="gitignore",
            help="Не учитывать правила .gitignore при сканировании",
        )
        gen_parser.add_argument(
            "-i",
            "--incremental",
            action="store_true",
            help="Инкрементальное обновление контекста (перестраивает индексы только для измененных в Git файлов)",
        )
        gen_parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Принудительно перезаписать файл, даже если содержимое не изменилось "
                "(игнорирует проверку volatile-полей: git_commit, generated_at, project_hash)"
            ),
        )
        gen_parser.add_argument(
            "--no-track",
            "--untracked",
            action="store_true",
            dest="untracked",
            help="Не сохранять запись об этом сгенерированном файле в .chutils/context_metadata.json",
        )
        gen_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик генерации контекста.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        # Используем stderr для статусных сообщений, чтобы не портить stdout (особенно для JSON)
        self.err_console.print(
            "[bold yellow]Генерация контекста API...[/bold yellow]", style="yellow"
        )

        if args.tree:
            self._handle_tree_index(args)
            return

        api_data: list[dict[str, Any]] = []
        examples = []
        project_name = "chutils"

        custom_ignore: list[str] = []
        if getattr(args, "ignore", None):
            for item in args.ignore:
                if "," in item:
                    custom_ignore.extend(p.strip() for p in item.split(",") if p.strip())
                else:
                    custom_ignore.append(item.strip())

        if args.project:
            # Сканируем внешний проект через статический AST-анализ
            project_path = Path(args.project).resolve()
            project_name = project_path.name
            try:
                from chutils.dev.ast_indexer import Indexer

                indexer = Indexer(
                    str(project_path),
                    custom_ignore=custom_ignore,
                    use_gitignore=bool(getattr(args, "gitignore", True)),
                )
                index = indexer.index(include_examples=bool(args.include_examples))

                api_data = self._collect_symbols_recursive(index.root)
                examples = index.examples
            except Exception as e:
                self.console.print(
                    f"[bold red]Ошибка при AST-анализе проекта {project_path}: {e}[/bold red]"
                )
                raise SystemExit(1)
        else:
            project_path = Path(".").resolve()
            # Получаем список всех публичных атрибутов chutils
            public_attrs = [attr for attr in dir(chutils) if not attr.startswith("_")]

            for attr_name in public_attrs:
                try:
                    obj = getattr(chutils, attr_name)
                    obj_type = "module"
                    signature = ""
                    doc = inspect.getdoc(obj) or ""

                    # Очистка мусорной документации для констант примитивных типов
                    if (
                            not inspect.isclass(obj)
                            and not inspect.isfunction(obj)
                            and not inspect.ismodule(obj)
                    ):
                        if isinstance(obj, (bool, int, float, str, type(None))):
                            if doc == inspect.getdoc(type(obj)):
                                doc = ""

                    summary = doc.split("\n")[0] if doc else ""

                    if inspect.isfunction(obj):
                        obj_type = "function"
                        try:
                            signature = str(inspect.signature(obj))
                        except ValueError:
                            signature = "(...)"
                    elif inspect.isclass(obj):
                        obj_type = "class"
                        try:
                            signature = str(inspect.signature(obj.__init__))
                            if signature == "(self, /)":
                                signature = "()"
                        except (ValueError, TypeError, AttributeError):
                            signature = "(...)"
                    elif inspect.ismodule(obj):
                        obj_type = "module"
                    else:
                        obj_type = "constant"

                    signature = re.sub(r" at 0x[0-9a-fA-F]+", "", signature)

                    api_data.append(
                        {
                            "name": attr_name,
                            "type": obj_type,
                            "signature": signature,
                            "summary": summary,
                            "full_doc": doc,
                        }
                    )
                except Exception as e:
                    self.console.print(
                        f"[dim red]Ошибка при анализе {attr_name}: {e}[/dim red]"
                    )

            if args.include_examples:
                try:
                    from chutils.dev.ast_indexer import Indexer

                    pkg_path = Path(chutils.__file__).parent
                    indexer = Indexer(str(pkg_path))
                    examples = indexer._collect_examples()
                except Exception as e:
                    self.console.print(
                        f"[dim red]Предупреждение: не удалось загрузить few-shot примеры: {e}[/dim red]"
                    )

        # Сортировка по имени
        api_data.sort(key=lambda x: x["name"])

        from chutils.dev.ast_indexer import collect_project_metadata
        metadata = collect_project_metadata(project_path)

        output_content = ""
        if args.format == "json":
            if args.include_examples:
                output_data = {
                    "metadata": metadata,
                    "api": api_data,
                    "examples": [
                        {
                            "name": ex.name,
                            "description": ex.description,
                            "good_pattern": ex.good_pattern,
                            "bad_pattern": ex.bad_pattern,
                        }
                        for ex in examples
                    ],
                }
                output_content = json.dumps(output_data, indent=2, ensure_ascii=False)
            else:
                output_data = {
                    "metadata": metadata,
                    "api": api_data,
                }
                output_content = json.dumps(output_data, indent=2, ensure_ascii=False)
        else:
            # Markdown
            frontmatter = (
                "---\n"
                f"chutils_version: {metadata['chutils_version']}\n"
                f"project_version: {metadata['project_version']}\n"
                f"git_commit: {metadata['git_commit']}\n"
                f"generated_at: {metadata['generated_at']}\n"
                f"project_hash: {metadata['project_hash']}\n"
                "---\n\n"
            )
            output_content = frontmatter + f"# Public API Map: {project_name}\n\n"

            headers = ["Name", "Type", "Signature", "Description"]
            rows = []
            for item in api_data:
                name = f"`{item['name']}`"
                obj_type = item["type"]
                sig = f"`{item['signature']}`" if item["signature"] else ""

                sig_escaped = sig.replace("|", "\\|")
                summary_escaped = item["summary"].replace("|", "\\|")
                summary_escaped = summary_escaped.replace("\n", " ").replace("\r", "")

                rows.append([name, obj_type, sig_escaped, summary_escaped])

            col_widths = []
            for i in range(len(headers)):
                max_len = len(headers[i])
                for row in rows:
                    max_len = max(max_len, len(row[i]))
                col_widths.append(max_len)

            header_line = "|" + "".join(f" {headers[i].ljust(col_widths[i])} |" for i in range(len(headers)))
            align_line = "|" + "|".join(f":{'-' * (col_widths[i] + 1)}" for i in range(len(headers))) + "|"

            output_content += header_line + "\n" + align_line + "\n"
            for row in rows:
                row_line = "|" + "".join(f" {row[i].ljust(col_widths[i])} |" for i in range(len(headers)))
                output_content += row_line + "\n"

            if args.include_examples and examples:
                output_content += "\n## Few-Shot Примеры (Образцы кода)\n"
                for ex in examples:
                    output_content += f"\n### Пример: {ex.name}\n"
                    if ex.description:
                        output_content += f"\n{ex.description}\n"
                    if ex.good_pattern:
                        output_content += f"\n#### Как надо (good_pattern.py)\n```python\n{ex.good_pattern}\n```\n"
                    if ex.bad_pattern:
                        output_content += f"\n#### Как не надо (bad_pattern.py)\n```python\n{ex.bad_pattern}\n```\n"

        untracked = bool(getattr(args, "untracked", False))
        target_type = "project" if args.project else "chutils"

        if args.output and not untracked:
            force: bool = getattr(args, "force", False)
            if not force and self._is_content_effectively_unchanged(output_content, args.output, args.format):
                self.err_console.print(
                    "[dim green] [SKIP] [/dim green] Содержимое не изменилось "
                    f"(кроме volatile-полей). Запись пропущена: [cyan]{args.output}[/cyan]. "
                    "Используйте [bold]--force[/bold] для принудительной перегенерации."
                )
                from chutils.dev.ast_indexer import save_context_metadata_cache
                save_context_metadata_cache(
                    project_path,
                    args.output,
                    args.format,
                    metadata["project_hash"],
                    target=target_type,
                    tree=bool(args.tree),
                    include_examples=bool(args.include_examples),
                    ignore=custom_ignore if custom_ignore else None,
                    project_arg=args.project,
                )
                return
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_content)
            self.console.print(
                f"[bold green] [OK] [/bold green] Контекст успешно сохранен в: [cyan]{args.output}[/cyan]"
            )
            from chutils.dev.ast_indexer import save_context_metadata_cache
            save_context_metadata_cache(
                project_path,
                args.output,
                args.format,
                metadata["project_hash"],
                target=target_type,
                tree=bool(args.tree),
                include_examples=bool(args.include_examples),
                ignore=custom_ignore if custom_ignore else None,
                project_arg=args.project,
            )
        else:
            if args.format == "json":
                print(output_content)
            else:
                self.console.print("\n" + output_content)

    def _collect_symbols_recursive(
            self, node: Any, current_prefix: str = ""
    ) -> list[dict[str, Any]]:
        """Рекурсивно собирает экспортируемые символы из AST индекса.

        Args:
            node: Узел AST дерева (ModuleNode).
            current_prefix: Текущий префикс имени модуля.

        Returns:
            Список словарей с метаданными символов.
        """
        symbols_data = []
        module_name = current_prefix + node.name if current_prefix else node.name

        for sym in node.symbols:
            if sym.layer != "private" and not sym.name.startswith("_"):
                symbols_data.append(
                    {
                        "name": f"{module_name}.{sym.name}",
                        "type": sym.type,
                        "signature": sym.signature or "",
                        "summary": sym.summary,
                        "full_doc": sym.docstring or "",
                    }
                )

        for child in node.children:
            prefix = f"{module_name}."
            symbols_data.extend(self._collect_symbols_recursive(child, prefix))

        return symbols_data

    @staticmethod
    def _normalize_for_comparison(content: str, fmt: str) -> str:
        """Нормализует содержимое файла, заменяя volatile-поля на плейсхолдер.

        Volatile-поля (git_commit, generated_at, project_hash) изменяются при
        каждом запуске, но не отражают реальных изменений в API проекта.
        Нормализация позволяет корректно сравнивать старое и новое содержимое.

        Args:
            content: Строковое содержимое файла.
            fmt: Формат файла ('markdown', 'json' или 'tree').

        Returns:
            Нормализованная строка для сравнения.
        """
        placeholder = "__VOLATILE__"
        if fmt == "markdown":
            for field in _VOLATILE_FIELDS:
                content = re.sub(
                    rf"^({re.escape(field)}:\s*).*$",
                    rf"\g<1>{placeholder}",
                    content,
                    flags=re.MULTILINE,
                )
        else:
            # JSON-форматы (json и tree)
            for field in _VOLATILE_FIELDS:
                content = re.sub(
                    rf'("{re.escape(field)}":\s*)"(?:[^"\\]|\\.)*"',
                    rf'\g<1>"{placeholder}"',
                    content,
                )
        return content

    def _is_content_effectively_unchanged(self, new_content: str, output_path: str, fmt: str) -> bool:
        """Проверяет, изменилось ли содержимое файла (игнорируя volatile-поля).

        Читает существующий файл по output_path и сравнивает нормализованное
        содержимое с новым сгенерированным содержимым.

        Args:
            new_content: Новое сгенерированное содержимое.
            output_path: Путь к существующему файлу.
            fmt: Формат файла ('markdown', 'json' или 'tree').

        Returns:
            True, если содержимое эффективно не изменилось, False иначе.
        """
        path = Path(output_path)
        if not path.exists():
            return False
        try:
            existing = path.read_text(encoding="utf-8")
        except Exception:
            return False
        return (
                self._normalize_for_comparison(existing, fmt)
                == self._normalize_for_comparison(new_content, fmt)
        )

    def _handle_tree_index(self, args: argparse.Namespace) -> None:
        """Генерация иерархического семантического индекса проекта.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from chutils.exceptions import OptionalDependencyError
        from chutils.env import has_pydantic

        if not has_pydantic():
            raise OptionalDependencyError(
                "Pydantic is required for generating hierarchical project index. "
                "Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'.",
                dependency="pydantic",
            )

        from chutils.dev.ast_indexer import Indexer

        custom_ignore: list[str] = []
        if getattr(args, "ignore", None):
            for item in args.ignore:
                if "," in item:
                    custom_ignore.extend(p.strip() for p in item.split(",") if p.strip())
                else:
                    custom_ignore.append(item.strip())

        try:
            if args.project:
                project_path = Path(args.project).resolve()
            else:
                project_path = Path(chutils.__file__).parent

            use_gitignore = bool(getattr(args, "gitignore", True))
            indexer = Indexer(str(project_path), custom_ignore=custom_ignore, use_gitignore=use_gitignore)

            if getattr(args, "incremental", False) and args.output and Path(args.output).exists():
                from chutils.dev.context.incremental import get_changed_files, update_tree_incrementally

                changed = get_changed_files(project_path)
                if changed:
                    self.err_console.print(
                        f"[dim cyan] [INCREMENTAL] [/dim cyan] Найдено {len(changed)} измененных файлов. Инкрементальное обновление..."
                    )
                    old_tree_data = json.loads(Path(args.output).read_text(encoding="utf-8"))
                    updated_dict = update_tree_incrementally(
                        old_tree_data,
                        changed,
                        Indexer,
                        project_path,
                        use_gitignore=use_gitignore,
                        custom_ignore=custom_ignore,
                    )
                    output_content = json.dumps(updated_dict, indent=2, ensure_ascii=False)
                else:
                    index = indexer.index(include_examples=bool(args.include_examples))
                    output_content = index.model_dump_json(indent=2)
            else:
                index = indexer.index(include_examples=bool(args.include_examples))
                output_content = index.model_dump_json(indent=2)

            if args.no_weights:
                try:
                    tree_dict = json.loads(output_content)
                    for edge in tree_dict.get("dependency_graph", []):
                        edge["weight"] = 1
                    output_content = json.dumps(tree_dict, indent=2, ensure_ascii=False)
                except Exception:
                    pass

            untracked = bool(getattr(args, "untracked", False))
            target_type = "project" if args.project else "chutils"

            if args.output and not untracked:
                tree_dict = json.loads(output_content)
                proj_hash = tree_dict.get("metadata", {}).get("project_hash", "") if isinstance(tree_dict, dict) else ""

                force: bool = getattr(args, "force", False)
                if not force and self._is_content_effectively_unchanged(output_content, args.output, "tree"):
                    self.err_console.print(
                        "[dim green] [SKIP] [/dim green] Содержимое не изменилось "
                        f"(кроме volatile-полей). Запись пропущена: [cyan]{args.output}[/cyan]. "
                        "Используйте [bold]--force[/bold] для принудительной перегенерации."
                    )
                    from chutils.dev.ast_indexer import save_context_metadata_cache
                    save_context_metadata_cache(
                        Path(".").resolve(),
                        args.output,
                        "tree",
                        proj_hash,
                        target=target_type,
                        tree=True,
                        include_examples=bool(args.include_examples),
                        ignore=custom_ignore if custom_ignore else None,
                        project_arg=args.project,
                    )
                    return
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output_content)
                self.console.print(
                    f"[bold green] [OK] [/bold green] Иерархический индекс успешно сохранен в: [cyan]{args.output}[/cyan]"
                )
                from chutils.dev.ast_indexer import save_context_metadata_cache
                save_context_metadata_cache(
                    Path(".").resolve(),
                    args.output,
                    "tree",
                    proj_hash,
                    target=target_type,
                    tree=True,
                    include_examples=bool(args.include_examples),
                    ignore=custom_ignore if custom_ignore else None,
                    project_arg=args.project,
                )
            else:
                print(output_content)

        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при генерации индекса:[/bold red] {e}"
            )
            raise SystemExit(1)
