from __future__ import annotations

from pathlib import Path

from ..ai_lint import Rule, LintResult


class EnvSyncRule(Rule):
    """Правило проверки соответствия состава ключей в .env и .env.example."""
    name = "EnvSyncRule"
    description = "Проверяет соответствие состава ключей переменных окружения в файлах .env и .env.example."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет проверку синхронизации файлов окружения.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных расхождений в составе ключей.
        """
        results: list[LintResult] = []
        base_path = Path(base_dir)

        try:
            from chutils.config.dev import load_ai_lint_config
            config = load_ai_lint_config()
            env_path = str(config.get("env_path", ".env"))
            example_path = str(config.get("example_path", ".env.example"))
        except Exception:
            env_path = ".env"
            example_path = ".env.example"

        env_abs_path = base_path / env_path
        example_abs_path = base_path / example_path

        # Если включен режим staged, проверяем, изменились ли .env или .env.example.
        # Если изменений нет (их нет в списке files), полностью пропускаем проверку.
        if getattr(self, "staged", False):
            env_abs_str = str(env_abs_path.resolve())
            example_abs_str = str(example_abs_path.resolve())
            if env_abs_str not in files and example_abs_str not in files:
                return results

        # Если ни один из файлов не существует, проверять нечего
        if not env_abs_path.exists() and not example_abs_path.exists():
            return results

        # Если существует один, но не существует другой
        if env_abs_path.exists() and not example_abs_path.exists():
            results.append(
                LintResult(
                    rule_name=self.name,
                    message=f"Файл {env_path} существует, но отсутствует шаблон {example_path}.",
                    severity=self.severity,
                    file_path=str(env_abs_path),
                    fix_suggestion=f"Создайте шаблон {example_path} или запустите синхронизацию: chutils dev sync-env"
                )
            )
            return results

        if not env_abs_path.exists() and example_abs_path.exists():
            results.append(
                LintResult(
                    rule_name=self.name,
                    message=f"Файл шаблона {example_path} существует, но отсутствует локальный {env_path}.",
                    severity=self.severity,
                    file_path=str(example_abs_path),
                    fix_suggestion=f"Создайте файл {env_path} на основе шаблона или запустите синхронизацию: chutils dev sync-env"
                )
            )
            return results

        # Оба файла существуют, сравним их ключи
        from chutils.dev.env_sync import check_env_sync
        try:
            diff = check_env_sync(env_abs_path, example_abs_path)
            if diff.has_diff():
                missing_msg = []
                if diff.missing_in_example:
                    missing_msg.append(
                        f"отсутствуют в {example_path}: {', '.join(diff.missing_in_example)}"
                    )
                if diff.missing_in_env:
                    missing_msg.append(
                        f"отсутствуют в {env_path}: {', '.join(diff.missing_in_env)}"
                    )

                message = f"Расхождение в ключах окружения: {'; '.join(missing_msg)}."
                results.append(
                    LintResult(
                        rule_name=self.name,
                        message=message,
                        severity=self.severity,
                        file_path=str(env_abs_path),
                        fix_suggestion="Синхронизируйте файлы: chutils dev sync-env"
                    )
                )
        except Exception as e:
            results.append(
                LintResult(
                    rule_name=self.name,
                    message=f"Ошибка при проверке соответствия ключей окружения: {e}",
                    severity=self.severity,
                    file_path=str(env_abs_path)
                )
            )

        return results
