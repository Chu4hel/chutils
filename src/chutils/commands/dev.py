from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
from typing import Any

import chutils
from .base import BaseCommand


class DevCommand(BaseCommand):
    """
    Команды для разработки и интеграции с AI.

    Позволяет генерировать контекстные данные о библиотеке для LLM.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует команду dev и её подкоманды в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        dev_parser = subparsers.add_parser(
            "dev",
            help="Инструменты разработчика и AI-контекст",
            description="Команды для генерации документации и контекста для LLM/AI агентов.",
        )
        dev_parser.set_defaults(handler=self.handle)
        dev_subparsers = dev_parser.add_subparsers(
            dest="subcommand", help="Доступные действия"
        )

        # dev generate-context
        gen_parser = dev_subparsers.add_parser(
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
        gen_parser.set_defaults(handler=self.handle_generate_context)

        # dev ai-lint
        lint_parser = dev_subparsers.add_parser(
            "ai-lint",
            help="Проверить AI-готовность кодовой базы",
            description="Проверяет наличие манифестов ИИ (antigravity.md, agents.md, gemini.md), качество docstrings/type hints и отсутствие секретов.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev ai-lint
  chutils dev ai-lint --strict
  chutils dev ai-lint --ignore "temp/,build/"
""",
        )
        lint_parser.add_argument(
            "--strict",
            action="store_true",
            default=None,
            help="Строгий режим: считать предупреждения ошибками и завершаться с ошибкой.",
        )
        lint_parser.add_argument(
            "--soft-mode",
            action="store_true",
            default=None,
            help="Мягкий режим: выводить проблемы, но возвращать успешный статус (0).",
        )
        lint_parser.add_argument(
            "--ignore", help="Список исключаемых путей (через запятую)."
        )
        lint_parser.add_argument(
            "--rules",
            help="Список запускаемых правил через запятую (по умолчанию все).",
        )
        lint_parser.add_argument(
            "--custom-rules-path", help="Путь к файлу с пользовательскими правилами."
        )
        lint_parser.set_defaults(handler=self.handle_ai_lint)

        # dev chat-context
        chat_parser = dev_subparsers.add_parser(
            "chat-context",
            help="Сгенерировать контекстный срез для ИИ-ассистента",
            description="Создает компактный Markdown-срез API, docstrings и examples для ИИ.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev chat-context -m logger,secret_manager
  chutils dev chat-context -t "logging and secrets" -l internal -o context.md
  chutils dev chat-context (интерактивный режим)
""",
        )
        chat_parser.add_argument(
            "-m",
            "--modules",
            help="Список модулей через запятую (например: logger,config).",
        )
        chat_parser.add_argument(
            "-t", "--task", help="Описание задачи или темы для автоподбора контекста."
        )
        chat_parser.add_argument(
            "-l",
            "--layer",
            choices=["public", "internal", "infrastructure", "private", "all"],
            default="public",
            help="Фильтр по слоям абстракции (по умолчанию: public)",
        )
        chat_parser.add_argument(
            "-o", "--output", help="Путь к файлу для сохранения результата."
        )
        chat_parser.set_defaults(handler=self.handle_chat_context)

        # dev scaffold
        scaffold_parser = dev_subparsers.add_parser(
            "scaffold",
            help="Инициализировать новый модуль Чистой Архитектуры",
            description="Создает структуру каталогов и базовые классы/интерфейсы Чистой Архитектуры.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev scaffold my_module
  chutils dev scaffold my_module -o ./src/my_module -f
""",
        )
        scaffold_parser.add_argument(
            "module_name",
            help="Имя создаваемого модуля (валидный Python-идентификатор)",
        )
        scaffold_parser.add_argument(
            "-o",
            "--output-dir",
            help="Базовый путь для создания каталога модуля (по умолчанию: ./[module_name])",
        )
        scaffold_parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Принудительно перезаписать файлы, если целевая директория уже существует",
        )
        scaffold_parser.set_defaults(handler=self.handle_scaffold)

        # dev mock
        mock_parser = dev_subparsers.add_parser(
            "mock",
            help="Запустить декларативный мок-сервер",
            description="Запускает легковесный многопоточный мок-сервер на основе mocks.yml.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev mock
  chutils dev mock init
  chutils dev mock -p 9000 -r my_mocks.yml --proxy-fallback https://api.example.com
""",
        )
        mock_parser.add_argument(
            "-p",
            "--port",
            type=int,
            default=8888,
            help="Порт мок-сервера (по умолчанию: 8888)",
        )
        mock_parser.add_argument(
            "-r",
            "--routes",
            default="mocks.yml",
            help="Путь к конфигурационному файлу роутов (по умолчанию: mocks.yml)",
        )
        mock_parser.add_argument(
            "--proxy-fallback",
            help="Базовый URL для проксирования ненайденных запросов (Reverse Proxy)",
        )

        # Добавим sub-subparsers для mock init
        mock_subparsers = mock_parser.add_subparsers(
            dest="mock_subcommand", help="Действия мок-сервера"
        )
        init_parser = mock_subparsers.add_parser(
            "init",
            help="Инициализировать шаблонный файл конфигурации роутов (mocks.yml)",
        )
        init_parser.add_argument(
            "-o",
            "--output",
            default="mocks.yml",
            help="Путь для сохранения файла (по умолчанию: mocks.yml)",
        )

        mock_parser.set_defaults(handler=self.handle_mock)

        # dev install-hooks
        hooks_parser = dev_subparsers.add_parser(
            "install-hooks",
            help="Установить pre-commit Git-хук для проверки ai-lint",
            description="Создает или обновляет pre-commit хук в .git/hooks для автоматического запуска ai-lint перед коммитами.",
        )
        hooks_parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Принудительно перезаписать существующий pre-commit хук.",
        )
        hooks_parser.add_argument(
            "--ruff",
            action="store_true",
            help="Добавить автоматическую проверку ruff check/format в pre-commit хук.",
        )
        hooks_parser.add_argument(
            "--flake8",
            action="store_true",
            help="Добавить проверку стиля flake8 в pre-commit хук.",
        )
        hooks_parser.set_defaults(handler=self.handle_install_hooks)

        # dev generate-few-shot
        few_shot_parser = dev_subparsers.add_parser(
            "generate-few-shot",
            help="Автогенерация few-shot примеров для целевого проекта",
            description="Анализирует проект, детектирует архитектурные абстракции и создает банк few-shot примеров в docs/ai_examples/.",
        )
        few_shot_parser.add_argument(
            "-p",
            "--project",
            required=True,
            help="Путь к корневой директории целевого проекта.",
        )
        few_shot_parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Принудительно перезаписать файлы при совпадении имен существующих категорий.",
        )
        few_shot_parser.set_defaults(handler=self.handle_generate_few_shot)

    def handle(self, args: argparse.Namespace) -> None:
        """Вызывается, если подкоманда не указана.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        self.console.print(
            "Используйте 'chutils dev --help' для просмотра доступных подкоманд."
        )

    def _collect_symbols_recursive(
            self, node: Any, current_prefix: str = ""
    ) -> list[dict[str, Any]]:
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

    def handle_generate_context(self, args: argparse.Namespace) -> None:
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

        if args.project:
            # Сканируем внешний проект через статический AST-анализ
            project_path = Path(args.project).resolve()
            project_name = project_path.name
            try:
                from chutils.dev.ast_indexer import Indexer

                indexer = Indexer(str(project_path))
                index = indexer.index(include_examples=bool(args.include_examples))

                api_data = self._collect_symbols_recursive(index.root)
                examples = index.examples
            except Exception as e:
                self.console.print(
                    f"[bold red]Ошибка при AST-анализе проекта {project_path}: {e}[/bold red]"
                )
                raise SystemExit(1)
        else:
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
                            # Если doc совпадает с docstring типа, значит это автогенерированный мусор
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

                    import re

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

        output_content = ""
        if args.format == "json":
            if args.include_examples:
                output_data = {
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
                output_content = json.dumps(api_data, indent=2, ensure_ascii=False)
        else:
            # Markdown
            output_content = f"# Public API Map: {project_name}\n\n"

            headers = ["Name", "Type", "Signature", "Description"]
            rows = []
            for item in api_data:
                name = f"`{item['name']}`"
                obj_type = item["type"]
                sig = f"`{item['signature']}`" if item["signature"] else ""

                # Экранируем '|' в сигнатуре и описании (summary), чтобы не ломать столбцы таблицы
                sig_escaped = sig.replace("|", "\\|")
                summary_escaped = item["summary"].replace("|", "\\|")
                # Убираем переводы строк из описания для сохранения табличного вида
                summary_escaped = summary_escaped.replace("\n", " ").replace("\r", "")

                rows.append([name, obj_type, sig_escaped, summary_escaped])

            # Вычисляем максимальную ширину столбцов
            col_widths = []
            for i in range(len(headers)):
                max_len = len(headers[i])
                for row in rows:
                    max_len = max(max_len, len(row[i]))
                col_widths.append(max_len)

            # Заголовок
            header_line = "|" + "".join(f" {headers[i].ljust(col_widths[i])} |" for i in range(len(headers)))
            # Разделитель с выравниванием по левому краю (:---) без лишних пробелов на стыках
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

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_content)
            self.console.print(
                f"[bold green] [OK] [/bold green] Контекст успешно сохранен в: [cyan]{args.output}[/cyan]"
            )
        else:
            if args.format == "json":
                # В stdout выводим чистый JSON для парсинга ИИ
                print(output_content)
            else:
                self.console.print("\n" + output_content)

    def _handle_tree_index(self, args: argparse.Namespace) -> None:
        """Генерация иерархического индекса (Phase 5)."""
        from chutils.exceptions import OptionalDependencyError
        from chutils.env import has_pydantic

        if not has_pydantic():
            raise OptionalDependencyError(
                "Pydantic is required for generating hierarchical project index. "
                "Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'.",
                dependency="pydantic",
            )

        from chutils.dev.ast_indexer import Indexer

        try:
            if args.project:
                project_path = Path(args.project).resolve()
            else:
                project_path = Path(chutils.__file__).parent

            indexer = Indexer(str(project_path))
            index = indexer.index(include_examples=bool(args.include_examples))

            # Если указано --no-weights, обнуляем веса в графе
            if args.no_weights:
                for edge in index.dependency_graph:
                    edge.weight = 1

            # Семантический индекс всегда в JSON
            output_content = index.model_dump_json(indent=2)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output_content)
                self.console.print(
                    f"[bold green] [OK] [/bold green] Иерархический индекс успешно сохранен в: [cyan]{args.output}[/cyan]"
                )
            else:
                # В stdout выводим чистый JSON для парсинга ИИ
                print(output_content)

        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при генерации индекса:[/bold red] {e}"
            )
            raise SystemExit(1)

    def handle_ai_lint(self, args: argparse.Namespace) -> None:
        """Обработчик проверки AI-готовности кодовой базы.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        cli_args: dict[str, Any] = {}
        if args.strict is not None:
            cli_args["strict"] = args.strict
        if args.soft_mode is not None:
            cli_args["soft_mode"] = args.soft_mode
        if args.ignore:
            cli_args["ignore"] = [
                i.strip() for i in args.ignore.split(",") if i.strip()
            ]
        if args.rules:
            cli_args["rules"] = [r.strip() for r in args.rules.split(",") if r.strip()]
        if args.custom_rules_path:
            cli_args["custom_rules_path"] = args.custom_rules_path

        # Ленивый импорт конфигурации и движка
        from chutils.config.dev import load_ai_lint_config
        from chutils.dev.ai_lint import LinterEngine

        try:
            config = load_ai_lint_config(cli_args=cli_args)
            engine = LinterEngine(config)

            self.err_console.print(
                "[bold yellow]Запуск аудита AI-готовности кодовой базы...[/bold yellow]"
            )
            results = engine.run()
            success = engine.print_results(results)

            if not success:
                raise SystemExit(1)
        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при выполнении ai-lint:[/bold red] {e}"
            )
            raise SystemExit(1)

    def handle_chat_context(self, args: argparse.Namespace) -> None:
        """Обработчик интерактивной сборки контекста.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from pathlib import Path
        from chutils.dev.chat_context import collect_context_slice, run_interactive_menu

        modules_list = None
        if args.modules:
            modules_list = [m.strip() for m in args.modules.split(",") if m.strip()]

        project_path = Path(".").resolve()

        # Если не указаны ни модули, ни задача, запускаем интерактивный режим
        if not modules_list and not args.task:
            modules_list = run_interactive_menu(project_path)
            if not modules_list:
                return

        self.err_console.print(
            "[bold yellow]Сборка контекстного среза...[/bold yellow]"
        )

        try:
            markdown_content = collect_context_slice(
                project_path=project_path,
                modules=modules_list,
                task=args.task,
                layer=args.layer,
            )

            if args.output:
                output_path = Path(args.output).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(markdown_content, encoding="utf-8")
                self.console.print(
                    f"[bold green] [OK] [/bold green] Контекстный срез успешно сохранен в: [cyan]{args.output}[/cyan]"
                )
            else:
                # В stdout выводим сгенерированный Markdown
                print(markdown_content)

        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при генерации контекста:[/bold red] {e}"
            )
            raise SystemExit(1)

    def handle_scaffold(self, args: argparse.Namespace) -> None:
        """Обработчик генерации структуры модуля.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        self.err_console.print(
            f"[bold yellow]Инициализация модуля Чистой Архитектуры '{args.module_name}'...[/bold yellow]"
        )
        from chutils.dev.scaffold import Scaffolder

        try:
            scaffolder = Scaffolder(
                module_name=args.module_name,
                output_dir=args.output_dir,
                force=args.force,
            )
            scaffolder.scaffold()
            self.console.print(
                f"[bold green] [OK] [/bold green] Модуль '{args.module_name}' успешно инициализирован."
            )
        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка инициализации:[/bold red] {e}"
            )
            raise SystemExit(1)

    def handle_mock(self, args: argparse.Namespace) -> None:
        """Обработчик мок-сервера.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from chutils.dev.mock_server import MockServerRunner

        try:
            runner = MockServerRunner(
                port=args.port,
                routes_path=args.routes,
                proxy_fallback=args.proxy_fallback,
            )
            if getattr(args, "mock_subcommand", None) == "init":
                runner.init_template(getattr(args, "output", "mocks.yml"))
            else:
                runner.run()
        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка мок-сервера:[/bold red] {e}"
            )
            raise SystemExit(1)

    def handle_install_hooks(self, args: argparse.Namespace) -> None:
        """Установка pre-commit хука.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        import os
        import sys
        from chutils.exceptions import ChutilsException

        current = Path(os.getcwd()).resolve()
        git_dir = None
        for parent in [current] + list(current.parents):
            potential_git = parent / ".git"
            if potential_git.exists() and potential_git.is_dir():
                git_dir = potential_git
                break

        if not git_dir:
            raise ChutilsException(
                "Директория '.git' не найдена. Убедитесь, что проект является Git-репозиторием "
                "и вы находитесь внутри него.",
                hint="Выполните 'git init', чтобы инициализировать репозиторий."
            )

        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path = hooks_dir / "pre-commit"

        # Подготовка вспомогательных вызовов ruff/flake8
        extra_checks = ""
        if getattr(args, "ruff", False):
            extra_checks += (
                "# Запуск ruff check & format\n"
                "if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then\n"
                "    uv run ruff check --fix && uv run ruff format\n"
                "elif [ -f poetry.lock ] && command -v poetry >/dev/null 2>&1; then\n"
                "    poetry run ruff check --fix && poetry run ruff format\n"
                "elif command -v ruff >/dev/null 2>&1; then\n"
                "    ruff check --fix && ruff format\n"
                "fi\n\n"
            )
        if getattr(args, "flake8", False):
            extra_checks += (
                "# Запуск flake8\n"
                "if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then\n"
                "    uv run flake8 .\n"
                "elif [ -f poetry.lock ] && command -v poetry >/dev/null 2>&1; then\n"
                "    poetry run flake8 .\n"
                "elif command -v flake8 >/dev/null 2>&1; then\n"
                "    flake8 .\n"
                "fi\n\n"
            )

        hook_template = (
            "#!/bin/sh\n"
            "# chutils pre-commit hook\n"
            "# === CHUTILS HOOK START ===\n"
            f"{extra_checks}"
            "# Автоматическое определение окружения и запуск ai-lint\n"
            "if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then\n"
            "    uv run chutils dev ai-lint\n"
            "elif [ -f poetry.lock ] && command -v poetry >/dev/null 2>&1; then\n"
            "    poetry run chutils dev ai-lint\n"
            "elif [ -f Pipfile ] && command -v pipenv >/dev/null 2>&1; then\n"
            "    pipenv run chutils dev ai-lint\n"
            "elif [ -d .venv ]; then\n"
            "    .venv/bin/chutils dev ai-lint || .venv/Scripts/chutils dev ai-lint || .venv/bin/python -m chutils dev ai-lint || .venv/Scripts/python -m chutils dev ai-lint\n"
            "elif [ -d venv ]; then\n"
            "    venv/bin/chutils dev ai-lint || venv/Scripts/chutils dev ai-lint || venv/bin/python -m chutils dev ai-lint || venv/Scripts/python -m chutils dev ai-lint\n"
            "elif command -v uv >/dev/null 2>&1; then\n"
            "    uv run chutils dev ai-lint\n"
            "elif command -v poetry >/dev/null 2>&1; then\n"
            "    poetry run chutils dev ai-lint\n"
            "elif command -v chutils >/dev/null 2>&1; then\n"
            "    chutils dev ai-lint\n"
            "else\n"
            "    python3 -m chutils dev ai-lint || python -m chutils dev ai-lint\n"
            "fi\n"
            "# === CHUTILS HOOK END ===\n"
        )

        if not hook_path.exists() or args.force:
            try:
                with open(hook_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(hook_template)
            except Exception as e:
                raise ChutilsException(f"Не удалось записать файл хука: {e}")
            self.console.print("[bold green]✓ Git-хук pre-commit успешно установлен![/bold green]")
        else:
            try:
                with open(hook_path, "r", encoding="utf-8", errors="ignore") as f:
                    existing_content = f.read()
            except Exception as e:
                raise ChutilsException(f"Не удалось прочитать существующий файл хука: {e}")

            if "# chutils pre-commit hook" in existing_content:
                self.console.print("[yellow]⚠ Git-хук chutils уже установлен в файле pre-commit.[/yellow]")
            else:
                try:
                    separator = "" if existing_content.endswith("\n") else "\n"
                    block = (
                        f"{separator}"
                        "# === CHUTILS HOOK START ===\n"
                        "# chutils pre-commit hook\n"
                        f"{extra_checks}"
                        "# Автоматическое определение окружения и запуск ai-lint\n"
                        "if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then\n"
                        "    uv run chutils dev ai-lint\n"
                        "elif [ -f poetry.lock ] && command -v poetry >/dev/null 2>&1; then\n"
                        "    poetry run chutils dev ai-lint\n"
                        "elif [ -f Pipfile ] && command -v pipenv >/dev/null 2>&1; then\n"
                        "    pipenv run chutils dev ai-lint\n"
                        "elif [ -d .venv ]; then\n"
                        "    .venv/bin/chutils dev ai-lint || .venv/Scripts/chutils dev ai-lint || .venv/bin/python -m chutils dev ai-lint || .venv/Scripts/python -m chutils dev ai-lint\n"
                        "elif [ -d venv ]; then\n"
                        "    venv/bin/chutils dev ai-lint || venv/Scripts/chutils dev ai-lint || venv/bin/python -m chutils dev ai-lint || venv/Scripts/python -m chutils dev ai-lint\n"
                        "elif command -v uv >/dev/null 2>&1; then\n"
                        "    uv run chutils dev ai-lint\n"
                        "elif command -v poetry >/dev/null 2>&1; then\n"
                        "    poetry run chutils dev ai-lint\n"
                        "elif command -v chutils >/dev/null 2>&1; then\n"
                        "    chutils dev ai-lint\n"
                        "else\n"
                        "    python3 -m chutils dev ai-lint || python -m chutils dev ai-lint\n"
                        "fi\n"
                        "# === CHUTILS HOOK END ===\n"
                    )
                    with open(hook_path, "a", encoding="utf-8", newline="\n") as f:
                        f.write(block)
                except Exception as e:
                    raise ChutilsException(f"Не удалось дописать в файл хука: {e}")
                self.console.print(
                    "[bold green]✓ Блок проверки chutils добавлен в существующий pre-commit хук![/bold green]")

        if sys.platform != "win32":
            try:
                current_mode = hook_path.stat().st_mode
                hook_path.chmod(current_mode | 0o111 | 0o444)
            except Exception as e:
                self.console.print(f"[yellow]⚠ Не удалось установить права chmod +x для хука: {e}[/yellow]")

    def handle_generate_few_shot(self, args: argparse.Namespace) -> None:
        """Обработчик автогенерации few-shot примеров.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from chutils.dev.generate_few_shot import generate_few_shot_bank

        try:
            generate_few_shot_bank(
                project_path=args.project,
                force=args.force,
                console=self.console,
            )
        except Exception as e:
            self.console.print(f"[bold red]Ошибка генерации few-shot банка:[/bold red] {e}")
            raise SystemExit(1)
