from __future__ import annotations

import ast
from pathlib import Path

from ..ai_lint import Rule, LintResult


class ChutilsIntegrationRule(Rule):
    """
    Правило поощрения использования встроенных механизмов chutils.
    """
    name = "ChutilsIntegrationRule"
    description = "Рекомендует использовать модули chutils (logger, config, secret_manager) вместо стандартных альтернатив."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет аудит использования стандартных библиотек вместо chutils.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список рекомендаций по интеграции с chutils.
        """
        results: list[LintResult] = []
        for file_path in files:
            if not file_path.endswith(".py"):
                continue
            if "tests" in Path(file_path).parts or "src/chutils/" in file_path.replace("\\", "/"):
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
            except Exception:
                continue

            # Предварительный сбор вызовов tempfile в файле
            has_tempfile_call = False
            for subnode in ast.walk(tree):
                if isinstance(subnode, ast.Call):
                    if isinstance(subnode.func, ast.Attribute) and subnode.func.attr in ("NamedTemporaryFile",
                                                                                         "mkstemp"):
                        has_tempfile_call = True
                        break
                    elif isinstance(subnode.func, ast.Name) and subnode.func.id in ("NamedTemporaryFile", "mkstemp"):
                        has_tempfile_call = True
                        break

            for node in ast.walk(tree):
                # Проверка импорта logging/keyring/requests/httpx
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if name.name == "logging":
                            results.append(
                                LintResult(
                                    rule_name=self.name,
                                    message="Импортирована стандартная библиотека 'logging'. Рекомендуется использовать 'chutils.setup_logger'.",
                                    severity=self.severity,
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    fix_suggestion="Используйте: from chutils import setup_logger; logger = setup_logger()"
                                )
                            )
                        elif name.name == "keyring":
                            results.append(
                                LintResult(
                                    rule_name=self.name,
                                    message="Импортирована внешняя библиотека 'keyring'. Рекомендуется использовать 'chutils.SecretManager'.",
                                    severity=self.severity,
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    fix_suggestion="Используйте: from chutils import SecretManager"
                                )
                            )
                        elif name.name == "requests":
                            results.append(
                                LintResult(
                                    rule_name=self.name,
                                    message="Импортирована внешняя библиотека 'requests'. Рекомендуется использовать 'chutils.web.WebClient' для умной ротации, лимитов и анти-детект возможностей.",
                                    severity=self.severity,
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    fix_suggestion="Используйте: from chutils.web import WebClient"
                                )
                            )
                        elif name.name == "httpx":
                            results.append(
                                LintResult(
                                    rule_name=self.name,
                                    message="Импортирована библиотека 'httpx'. Рекомендуется использовать 'chutils.web.WebClient' или 'chutils.web.AsyncWebClient' для ротации User-Agent, прокси и контроля лимитов.",
                                    severity=self.severity,
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    fix_suggestion="Используйте: from chutils.web import WebClient, AsyncWebClient"
                                )
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module == "logging":
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message="Импортированы элементы из стандартного 'logging'. Используйте 'chutils.setup_logger'.",
                                severity=self.severity,
                                file_path=file_path,
                                line_number=node.lineno,
                                fix_suggestion="Настройте логирование через 'setup_logger' из chutils."
                            )
                        )
                    elif node.module == "keyring":
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message="Импортированы элементы из 'keyring'. Используйте 'chutils.SecretManager'.",
                                severity=self.severity,
                                file_path=file_path,
                                line_number=node.lineno,
                                fix_suggestion="Используйте 'SecretManager' из chutils."
                            )
                        )
                    elif node.module == "requests":
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message="Импортированы элементы из 'requests'. Рекомендуется использовать 'chutils.web.WebClient'.",
                                severity=self.severity,
                                file_path=file_path,
                                line_number=node.lineno,
                                fix_suggestion="Используйте 'WebClient' из chutils.web."
                            )
                        )
                    elif node.module == "httpx":
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message="Импортированы элементы из 'httpx'. Рекомендуется использовать 'chutils.web.WebClient' или 'chutils.web.AsyncWebClient'.",
                                severity=self.severity,
                                file_path=file_path,
                                line_number=node.lineno,
                                fix_suggestion="Используйте 'WebClient' или 'AsyncWebClient' из chutils.web."
                            )
                        )
                # Проверка os.getenv/os.environ
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name) and node.value.id == "os" and node.attr in ("environ",
                                                                                                    "getenv"):
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"Используется прямое обращение к 'os.{node.attr}'. Рекомендуется использовать 'chutils.config'.",
                                severity=self.severity,
                                file_path=file_path,
                                line_number=node.lineno,
                                fix_suggestion="Получайте конфигурацию через 'chutils.get_config_value'."
                            )
                        )
                # Проверка mkdir(parents=True, exist_ok=True)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "mkdir":
                    has_parents_true = False
                    has_exist_ok_true = False
                    for kw in node.keywords:
                        if kw.arg == "parents" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            has_parents_true = True
                        elif kw.arg == "exist_ok" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            has_exist_ok_true = True
                    if has_parents_true and has_exist_ok_true:
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message="Используется ручной вызов '.mkdir(parents=True, exist_ok=True)'. Рекомендуется использовать 'chutils.fs.ensure_dir'.",
                                severity=self.severity,
                                file_path=file_path,
                                line_number=node.lineno,
                                fix_suggestion="Используйте: from chutils.fs import ensure_dir; ensure_dir(path)"
                            )
                        )
                # Проверка write_text/write_bytes и других паттернов атомарной записи
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("write_text", "write_bytes"):
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"Используется метод '.{node.func.attr}()'. Рекомендуется использовать безопасную атомарную запись 'chutils.fs.atomic_write'.",
                                severity=self.severity,
                                file_path=file_path,
                                line_number=node.lineno,
                                fix_suggestion="Используйте: from chutils.fs import atomic_write; atomic_write(file_path, data)"
                            )
                        )
                    elif node.func.attr in ("replace", "rename", "move") and has_tempfile_call:
                        is_os_or_shutil = False
                        if isinstance(node.func.value, ast.Name) and node.func.value.id in ("os", "shutil"):
                            is_os_or_shutil = True
                        if is_os_or_shutil:
                            results.append(
                                LintResult(
                                    rule_name=self.name,
                                    message=f"Обнаружен паттерн ручной атомарной записи через tempfile и '{node.func.value.id}.{node.func.attr}'. Рекомендуется использовать 'chutils.fs.atomic_write'.",
                                    severity=self.severity,
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    fix_suggestion="Используйте: from chutils.fs import atomic_write; atomic_write(file_path, data)"
                                )
                            )
                    elif node.func.attr in ("dump", "dump_all"):
                        if isinstance(node.func.value, ast.Name) and node.func.value.id in ("json", "yaml"):
                            results.append(
                                LintResult(
                                    rule_name=self.name,
                                    message=f"Прямой вызов '{node.func.value.id}.{node.func.attr}' для записи файла. Рекомендуется использовать 'chutils.fs.atomic_write' с автоматической сериализацией.",
                                    severity=self.severity,
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    fix_suggestion="Используйте: from chutils.fs import atomic_write; atomic_write(file_path, data)"
                                )
                            )
        return results
