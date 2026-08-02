from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .base import BaseCommand
from ..cli_utils import get_console


class CheckCommand(BaseCommand):
    """
    Команда сводной проверки проекта: система (health check), конфигурация (validate) и AI-линтер (ai-lint).
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует команду check и псевдоним doctor в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        check_parser = subparsers.add_parser(
            "check",
            aliases=["doctor"],
            help="Комплексная проверка проекта (система, конфигурация, AI-аудит)",
            description=(
                "Единая команда для полной проверки проекта. Объединяет системный Health Check, "
                "валидацию Pydantic-конфигурации и статический аудит AI-готовности (ai-lint)."
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils check                # Выполнить полный аудит всего проекта
  chutils doctor               # Псевдоним команды check
  chutils check --config       # Проверить только валидацию Pydantic-конфигурации
  chutils check --lint         # Проверить только AI-готовность кода (ai-lint)
  chutils check --system       # Запустить только системный Health Check
  chutils check --json         # Вывести единый сводный отчёт в формате JSON
""",
        )
        check_parser.add_argument(
            "--config",
            action="store_true",
            help="Выполнить только валидацию Pydantic-конфигурации",
        )
        check_parser.add_argument(
            "--lint",
            "--ai",
            dest="lint",
            action="store_true",
            help="Выполнить только статический аудит AI-готовности (ai-lint)",
        )
        check_parser.add_argument(
            "--system",
            "--health",
            dest="system",
            action="store_true",
            help="Выполнить только системный Health Check среды",
        )
        check_parser.add_argument(
            "-m", "--model",
            help="Путь к Pydantic-модели для проверки конфигурации (например, 'myapp.config:Settings')",
        )
        check_parser.add_argument(
            "--json",
            action="store_true",
            help="Вывести результаты проверок в формате JSON",
        )
        check_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик комплексной проверки проекта.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        console = get_console()

        # Определяем, какие именно компоненты запускать
        run_all = not (args.config or args.lint or args.system)
        run_system = run_all or args.system
        run_config = run_all or args.config
        run_lint = run_all or args.lint

        results: dict[str, Any] = {
            "status": "HEALTHY",
            "checks": {},
        }
        has_errors = False

        if not args.json:
            console.print("[bold cyan]=== Комплексная проверка проекта (chutils check) ===[/bold cyan]\n")

        # 1. Системная диагностика (Health Check)
        if run_system:
            from chutils.diagnostics.manager import default_manager
            diag_report = default_manager.run_checks_sync()

            status_str = str(getattr(diag_report.status, "value", diag_report.status))
            passed_count = getattr(diag_report, "passed_checks", len([c for c in getattr(diag_report, "checks", []) if
                                                                      getattr(c, "status", None) == "HEALTHY"]))
            total_count = getattr(diag_report, "total_checks", len(getattr(diag_report, "checks", [])))
            duration = getattr(diag_report, "total_duration", getattr(diag_report, "total_duration_sec", 0.0))

            results["checks"]["system"] = {
                "status": status_str,
                "duration_sec": duration,
                "summary": {"passed": passed_count, "total": total_count},
            }
            if status_str == "UNHEALTHY":
                has_errors = True
                results["status"] = "UNHEALTHY"

            if not args.json:
                console.print("[bold yellow]1. Системный Health Check:[/bold yellow]")
                status_color = "green" if status_str == "HEALTHY" else "red"
                console.print(f"Статус системы: [{status_color}]{status_str}[/{status_color}]")
                console.print(f"Успешных проверок: {passed_count}/{total_count}\n")

        # 2. Валидация Pydantic конфигурации
        if run_config:
            from chutils.commands.utils import _import_string, ensure_project_paths_in_sys_path
            from chutils.config import get_config
            from chutils.env import PYDANTIC_AVAILABLE

            ensure_project_paths_in_sys_path()

            config_result: dict[str, Any] = {"status": "SUCCESS", "message": ""}
            if not PYDANTIC_AVAILABLE:
                config_result = {
                    "status": "FAILED",
                    "error": "Пакет 'pydantic' не установлен. Установите: pip install chutils[pydantic]",
                }
                has_errors = True
            else:
                model_class = None
                model_name = args.model
                if model_name:
                    model_class = _import_string(model_name)
                    if model_class is None:
                        config_result = {
                            "status": "FAILED",
                            "error": f"Не удалось импортировать модель '{model_name}'.",
                        }
                        has_errors = True
                else:
                    search_paths = [
                        "src.context:Settings",
                        "src.config:Settings",
                        "context:Settings",
                        "config:Settings",
                    ]
                    for path in search_paths:
                        cls = _import_string(path)
                        if cls is not None:
                            model_class = cls
                            model_name = path
                            break

                if model_class is None and not config_result.get("error"):
                    config_result = {
                        "status": "WARNING",
                        "message": "Pydantic модель Settings не найдена автоматически (укажите через --model)",
                    }
                elif model_class is not None:
                    try:
                        get_config(model=model_class)
                        config_result = {
                            "status": "SUCCESS",
                            "model": model_name,
                            "message": f"Конфигурация успешно прошла валидацию по модели '{model_name}'",
                        }
                    except Exception as e:
                        config_result = {
                            "status": "FAILED",
                            "model": model_name,
                            "error": str(e),
                        }
                        has_errors = True

            results["checks"]["config"] = config_result

            if not args.json:
                console.print("[bold yellow]2. Валидация конфигурации Pydantic:[/bold yellow]")
                if config_result["status"] == "SUCCESS":
                    console.print(f"[bold green]✓ {config_result['message']}[/bold green]\n")
                elif config_result["status"] == "WARNING":
                    console.print(f"[yellow]⚠ {config_result['message']}[/yellow]\n")
                else:
                    console.print(f"[bold red]✗ Ошибка валидации: {config_result.get('error')}[/bold red]\n")

        # 3. AI-Readiness аудит (ai-lint)
        if run_lint:
            from chutils.config.dev import load_ai_lint_config
            from chutils.dev.ai_lint import LinterEngine

            lint_config = load_ai_lint_config()
            lint_config["base_dir"] = str(Path.cwd())
            engine = LinterEngine(lint_config)
            engine.load_rules()

            lint_results = engine.run()

            errors_count = sum(1 for r in lint_results if r.severity == "error")
            warns_count = sum(1 for r in lint_results if r.severity == "warn")

            lint_status = "SUCCESS"
            if errors_count > 0:
                lint_status = "FAILED"
                has_errors = True
            elif warns_count > 0:
                lint_status = "WARNING"

            results["checks"]["lint"] = {
                "status": lint_status,
                "total_issues": len(lint_results),
                "errors": errors_count,
                "warnings": warns_count,
            }

            if not args.json:
                console.print("[bold yellow]3. Аудит AI-готовности (ai-lint):[/bold yellow]")
                if lint_status == "SUCCESS":
                    console.print("[bold green]✓ Все проверки AI-готовности пройдены![/bold green]\n")
                elif lint_status == "WARNING":
                    console.print(f"[yellow]⚠ Найдено предупреждений: {warns_count}[/yellow]\n")
                else:
                    console.print(
                        f"[bold red]✗ Найдено ошибок: {errors_count}, предупреждений: {warns_count}[/bold red]\n")

        if args.json:
            import json
            console.print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            if has_errors:
                console.print("[bold red]Вывод: Проект содержит ошибки! Проверьте детали выше.[/bold red]")
                raise SystemExit(1)
            else:
                console.print("[bold green]Вывод: Все проверенные компоненты проекта в порядке![/bold green]")
