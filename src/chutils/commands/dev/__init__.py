from __future__ import annotations

import argparse
from typing import Any

from .base import SubCommand
from ..base import BaseCommand


def get_subcommands() -> list[type[SubCommand]]:
    """Возвращает список всех классов подкоманд dev с ленивой загрузкой.

    Returns:
        Список классов, унаследованных от SubCommand.
    """
    from .generate_context import GenerateContextSubCommand
    from .ai_lint import AiLintSubCommand
    from .chat_context import ChatContextSubCommand
    from .scaffold import ScaffoldSubCommand
    from .mock import MockSubCommand
    from .hooks import HooksSubCommand
    from .few_shot import FewShotSubCommand
    from .diagnostics import DiagnosticsSubCommand
    from .sync_env import SyncEnvSubCommand
    from .profile_imports import ProfileImportsSubCommand
    from .dashboard import DashboardSubCommand
    from .setup_github_actions import SetupGithubActionsSubCommand
    from .clean import CleanSubCommand
    from .watch import WatchSubCommand
    from .lock import LockSubCommand

    return [
        GenerateContextSubCommand,
        AiLintSubCommand,
        ChatContextSubCommand,
        ScaffoldSubCommand,
        MockSubCommand,
        HooksSubCommand,
        FewShotSubCommand,
        DiagnosticsSubCommand,
        SyncEnvSubCommand,
        ProfileImportsSubCommand,
        DashboardSubCommand,
        SetupGithubActionsSubCommand,
        CleanSubCommand,
        WatchSubCommand,
        LockSubCommand,
    ]


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
  chutils dev ai-lint --rules ChutilsIntegrationRule,ManifestRule
  chutils dev ai-lint --staged

Подавление срабатываний для отдельной строки:
  Добавьте комментарий в конец строки или строкой выше:
    import logging  # chutils: ignore[ChutilsIntegrationRule]
    code()          # chutils: ignore[RuleA, RuleB]
    # chutils: ignore[ChutilsIntegrationRule]
    some_call()
    code()          # chutils: ignore[all]   <- все правила

Доступные правила по умолчанию:
  ManifestRule, DocstringQualityRule, SecurityHardcodeRule,
  ChutilsIntegrationRule, APIMapRule, EnvSyncRule, CodeDecompositionRule,
  APIMapHashRule, FileDependencySyncRule, UpgradeCheckRule, LinterCoverageRule
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
        lint_parser.add_argument(
            "--staged",
            action="store_true",
            help="Проверять только файлы, подготовленные к коммиту (staged) в Git.",
        )
        lint_parser.add_argument(
            "--output-format",
            choices=["default", "table"],
            default=None,
            help="Формат вывода результатов (по умолчанию: table).",
        )
        lint_parser.add_argument(
            "--group-by",
            choices=["file", "rule"],
            default=None,
            help="Группировка вывода результатов (по умолчанию: file).",
        )
        lint_parser.add_argument(
            "--exclude-rules",
            help="Список исключаемых правил через запятую.",
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

        # dev diagnostics
        diagnostics_parser = dev_subparsers.add_parser(
            "diagnostics",
            help="Запустить диагностику и проверку работоспособности среды (Health Check)",
            description="Выполняет встроенные и пользовательские проверки среды (keyring, конфигурация и др.) с выводом отчета.",
        )
        diagnostics_parser.add_argument(
            "--json",
            action="store_true",
            help="Вывести отчет в формате JSON",
        )
        diagnostics_parser.set_defaults(handler=self.handle_diagnostics)

        # dev sync-env
        sync_parser = dev_subparsers.add_parser(
            "sync-env",
            help="Синхронизировать .env и .env.example",
            description="Синхронизирует переменные окружения между локальным .env и шаблоном .env.example.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev sync-env --dry-run
  chutils dev sync-env --yes
  chutils dev sync-env --env-path .env.dev --example-path .env.dev.example
""",
        )
        sync_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать расхождения без физического изменения файлов",
        )
        sync_parser.add_argument(
            "-y",
            "--yes",
            "--force",
            dest="force",
            action="store_true",
            help="Применить изменения автоматически без интерактивного подтверждения",
        )
        sync_parser.add_argument(
            "--env-path",
            help="Путь к файлу .env (по умолчанию: .env)",
        )
        sync_parser.add_argument(
            "--example-path",
            help="Путь к файлу .env.example (по умолчанию: .env.example)",
        )
        sync_parser.set_defaults(handler=self.handle_sync_env)

        # dev profile-imports
        profile_parser = dev_subparsers.add_parser(
            "profile-imports",
            help="Профилировать время холодного старта и импорта модулей",
            description="Запускает профилирование времени импорта с флагом -X importtime, анализирует вывод и отображает дерево импортов или таблицы зависимостей.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev profile-imports
  chutils dev profile-imports chutils.logger -t 0.5
  chutils dev profile-imports --table
  chutils dev profile-imports --json
""",
        )
        profile_parser.add_argument(
            "target",
            nargs="?",
            default="chutils",
            help="Имя целевого модуля или путь к файлу для импорта (по умолчанию: chutils)",
        )
        profile_parser.add_argument(
            "-t",
            "--threshold",
            type=float,
            default=1.0,
            help="Порог времени импорта в миллисекундах для скрытия мелких веток (по умолчанию: 1.0)",
        )
        profile_parser.add_argument(
            "--table",
            action="store_true",
            help="Вывести плоскую таблицу импортов, отсортированную по собственному времени",
        )
        profile_parser.add_argument(
            "--json",
            action="store_true",
            help="Вывести распарсенную структуру данных в формате JSON",
        )
        profile_parser.set_defaults(handler=self.handle_profile_imports)

        # dev dashboard
        dashboard_parser = dev_subparsers.add_parser(
            "dashboard",
            help="Запустить интерактивный TUI-дашборд CLI команд",
            description="Отображает интерактивный консольный дашборд для просмотра, заполнения параметров и запуска CLI-команд проекта.",
        )
        dashboard_parser.set_defaults(handler=self.handle_dashboard)

        # dev setup-github-actions
        setup_gha_parser = dev_subparsers.add_parser(
            "setup-github-actions",
            help="Интерактивная настройка и генерация GitHub Actions",
            description="Генерирует и настраивает workflow для GitHub Actions на основе setup-uv.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        interactive_group = setup_gha_parser.add_mutually_exclusive_group()
        interactive_group.add_argument(
            "--interactive",
            action="store_true",
            dest="interactive",
            default=True,
            help="Запустить интерактивную настройку (по умолчанию)"
        )
        interactive_group.add_argument(
            "--no-interactive",
            action="store_false",
            dest="interactive",
            help="Отключить интерактивный опрос"
        )

        setup_gha_parser.add_argument(
            "--python-versions",
            default="3.10,3.11,3.12,3.13",
            help="Список версий Python через запятую (например, 3.10,3.11,3.12,3.13)"
        )

        pytest_group = setup_gha_parser.add_mutually_exclusive_group()
        pytest_group.add_argument("--with-pytest", action="store_true", dest="with_pytest", default=None)
        pytest_group.add_argument("--without-pytest", action="store_false", dest="with_pytest", default=None)

        mypy_group = setup_gha_parser.add_mutually_exclusive_group()
        mypy_group.add_argument("--with-mypy", action="store_true", dest="with_mypy", default=None)
        mypy_group.add_argument("--without-mypy", action="store_false", dest="with_mypy", default=None)

        ruff_group = setup_gha_parser.add_mutually_exclusive_group()
        ruff_group.add_argument("--with-ruff", action="store_true", dest="with_ruff", default=None)
        ruff_group.add_argument("--without-ruff", action="store_false", dest="with_ruff", default=None)

        ailint_group = setup_gha_parser.add_mutually_exclusive_group()
        ailint_group.add_argument("--with-ai-lint", action="store_true", dest="with_ai_lint", default=None)
        ailint_group.add_argument("--without-ai-lint", action="store_false", dest="with_ai_lint", default=None)

        setup_gha_parser.add_argument(
            "--output-file",
            default=".github/workflows/ci.yml",
            help="Путь для сохранения сгенерированного workflow (по умолчанию: .github/workflows/ci.yml)"
        )

        setup_gha_parser.set_defaults(handler=self.handle_setup_github_actions)

        # dev clean
        clean_parser = dev_subparsers.add_parser(
            "clean",
            help="Очистить проект от временных файлов и кэшей",
            description="Сканирует проект и безопасно удаляет файлы кэшей (__pycache__, .pytest_cache, .mypy_cache, .ruff_cache, .coverage, build/, dist/ и др.).",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev clean
  chutils dev clean --dry-run
  chutils dev clean --yes
  chutils dev clean --exclude ".venv,node_modules" --include "temp_dir/,*.log"
""",
        )
        clean_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать список удаляемых файлов и суммарный объем без физического удаления.",
        )
        clean_parser.add_argument(
            "-y",
            "--yes",
            "--force",
            dest="force",
            action="store_true",
            help="Удалить файлы без интерактивного подтверждения.",
        )
        clean_parser.add_argument(
            "-e",
            "--exclude",
            help="Список исключаемых путей или шаблонов (через запятую).",
        )
        clean_parser.add_argument(
            "-i",
            "--include",
            help="Список дополнительных путей или шаблонов для очистки (через запятую).",
        )
        clean_parser.set_defaults(handler=self.handle_clean)

        # dev watch
        watch_parser = dev_subparsers.add_parser(
            "watch",
            help="Live Dev режим с автоматическим hot-reload при изменении файлов",
            description="Отслеживает изменения файлов в проекте и автоматически перезапускает процесс или функцию.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev watch -- python main.py
  chutils dev watch -m myapp.main:start
  chutils dev watch -p src -e py,yaml -- python main.py
""",
        )
        watch_parser.add_argument(
            "-p",
            "--path",
            action="append",
            dest="paths",
            help="Директория или файл для отслеживания (можно указывать несколько раз, по умолчанию: .)",
        )
        watch_parser.add_argument(
            "-e",
            "--extensions",
            help="Список расширений файлов через запятую (по умолчанию: py,yaml,yml,json,toml,ini)",
        )
        watch_parser.add_argument(
            "--ignore",
            help="Шаблоны путей для игнорирования через запятую",
        )
        watch_parser.add_argument(
            "-d",
            "--debounce",
            type=float,
            default=0.5,
            help="Интервал дебаунса перед перезапуском в секундах (по умолчанию: 0.5)",
        )
        watch_parser.add_argument(
            "-m",
            "--module",
            help="Целевая функция для внутрипроцессного перезапуска в формате 'module.path:func_name'",
        )
        watch_parser.add_argument(
            "command",
            nargs=argparse.REMAINDER,
            help="Команда для запуска в дочернем процессе (указывается после '--')",
        )
        watch_parser.set_defaults(handler=self.handle_watch)

        # dev lock
        lock_parser = dev_subparsers.add_parser(
            "lock",
            help="Перегенерировать весь контекст проекта из реестра",
            description=(
                "Читает реестр .chutils/context_metadata.json и автоматически перегенерирует "
                "все зарегистрированные ранее файлы контекста."
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev lock
  chutils dev lock --force
""",
        )
        lock_parser.add_argument(
            "--force",
            action="store_true",
            help="Принудительно перезаписать все файлы, даже если содержимое не изменилось",
        )
        lock_parser.set_defaults(handler=self.handle_lock)

    def handle(self, args: argparse.Namespace) -> None:
        """Вызывается, если подкоманда не указана.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        self.console.print(
            "Используйте 'chutils dev --help' для просмотра доступных подкоманд."
        )

    def handle_generate_context(self, args: argparse.Namespace) -> None:
        """Обработчик генерации контекста API.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .generate_context import GenerateContextSubCommand
        GenerateContextSubCommand().handle(args)

    def handle_ai_lint(self, args: argparse.Namespace) -> None:
        """Обработчик проверки AI-готовности кодовой базы.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .ai_lint import AiLintSubCommand
        AiLintSubCommand().handle(args)

    def handle_chat_context(self, args: argparse.Namespace) -> None:
        """Обработчик интерактивной сборки контекста.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .chat_context import ChatContextSubCommand
        ChatContextSubCommand().handle(args)

    def handle_scaffold(self, args: argparse.Namespace) -> None:
        """Обработчик генерации структуры модуля.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .scaffold import ScaffoldSubCommand
        ScaffoldSubCommand().handle(args)

    def handle_mock(self, args: argparse.Namespace) -> None:
        """Обработчик мок-сервера.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .mock import MockSubCommand
        MockSubCommand().handle(args)

    def handle_install_hooks(self, args: argparse.Namespace) -> None:
        """Обработчик установки Git-хуков.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .hooks import HooksSubCommand
        HooksSubCommand().handle(args)

    def handle_generate_few_shot(self, args: argparse.Namespace) -> None:
        """Обработчик генерации few-shot примеров.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .few_shot import FewShotSubCommand
        FewShotSubCommand().handle(args)

    def handle_diagnostics(self, args: argparse.Namespace) -> None:
        """Обработчик запуска диагностики.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .diagnostics import DiagnosticsSubCommand
        DiagnosticsSubCommand().handle(args)

    def handle_sync_env(self, args: argparse.Namespace) -> None:
        """Обработчик синхронизации env-файлов.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .sync_env import SyncEnvSubCommand
        SyncEnvSubCommand().handle(args)

    def handle_profile_imports(self, args: argparse.Namespace) -> None:
        """Обработчик профилирования импортов.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .profile_imports import ProfileImportsSubCommand
        ProfileImportsSubCommand().handle(args)

    def handle_dashboard(self, args: argparse.Namespace) -> None:
        """Обработчик интерактивного TUI-дашборда.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .dashboard import DashboardSubCommand
        DashboardSubCommand().handle(args)

    def handle_setup_github_actions(self, args: argparse.Namespace) -> None:
        """Обработчик интерактивной настройки и генерации GitHub Actions.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .setup_github_actions import SetupGithubActionsSubCommand
        SetupGithubActionsSubCommand().handle(args)

    def handle_clean(self, args: argparse.Namespace) -> None:
        """Обработчик уборки мусора разработки (chutils dev clean).

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .clean import CleanSubCommand
        CleanSubCommand().handle(args)

    def handle_watch(self, args: argparse.Namespace) -> None:
        """Обработчик Live Dev режима с hot-reload (chutils dev watch).

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .watch import WatchSubCommand
        WatchSubCommand().handle(args)

    def handle_lock(self, args: argparse.Namespace) -> None:
        """Обработчик автоматической перегенерации файлов контекста (chutils dev lock).

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from .lock import LockSubCommand
        LockSubCommand().handle(args)
