"""
Встроенные правила проверки кодовой базы (ai-lint).
Содержит конкретные реализации правил ManifestRule, DocstringQualityRule,
SecurityHardcodeRule, ChutilsIntegrationRule и APIMapRule.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from .ai_lint import Rule, LintResult


class ManifestRule(Rule):
    """
    Правило проверки наличия манифестов для ИИ (antigravity.md, agents.md, GEMINI.md).
    """
    name = "ManifestRule"
    description = "Проверяет наличие файлов манифестов ИИ (antigravity.md, agents.md, GEMINI.md) в ключевых директориях."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет проверку наличия файлов манифеста ИИ.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных предупреждений по манифестам.
        """
        results: list[LintResult] = []
        base_path = Path(base_dir)

        default_manifests = [
            "GEMINI.md", "gemini.md",
            "antigravity.md", "ANTIGRAVITY.md",
            "agents.md", "AGENTS.md"
        ]

        # 1. Проверяем корень проекта
        root_found = False
        for name in default_manifests:
            if (base_path / name).exists():
                root_found = True
                break

        if not root_found:
            results.append(
                LintResult(
                    rule_name=self.name,
                    message="Отсутствует корневой файл манифеста ИИ (antigravity.md, agents.md или GEMINI.md).",
                    severity=self.severity,
                    file_path=str(base_path / "antigravity.md"),
                    fix_suggestion="Создайте файл манифеста (например, antigravity.md или agents.md) в корне проекта для описания архитектуры и соглашений для ИИ."
                )
            )

        # 2. Проверяем основные пакеты (первый уровень под src/)
        src_dir = base_path / "src"
        if src_dir.exists():
            for p in src_dir.iterdir():
                if p.is_dir() and (p / "__init__.py").exists():
                    pkg_found = False
                    for name in default_manifests:
                        if (p / name).exists():
                            pkg_found = True
                            break
                    if not pkg_found:
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"В основном пакете {p.name} отсутствует файл манифеста ИИ.",
                                severity=self.severity,
                                file_path=str(p / "antigravity.md"),
                                fix_suggestion=f"Рекомендуется добавить файл манифеста (например, antigravity.md или agents.md) в директорию пакета {p.name}."
                            )
                        )
        return results


class DocstringVisitor(ast.NodeVisitor):
    """
    Вспомогательный AST-посетитель для проверки docstrings и type hints.
    """

    def __init__(self, file_path: str, rule_name: str) -> None:
        """Инициализирует AST-посетитель docstring'ов.

        Args:
            file_path: Путь к анализируемому файлу.
            rule_name: Название запускаемого правила.
        """
        self.file_path = file_path
        self.rule_name = rule_name
        self.issues: list[LintResult] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Анализирует класс на наличие docstring.

        Args:
            node: AST-узел определения класса.
        """
        if not node.name.startswith("_"):
            doc = ast.get_docstring(node)
            if not doc:
                self.issues.append(
                    LintResult(
                        rule_name=self.rule_name,
                        message=f"У публичного класса {node.name} отсутствует docstring.",
                        severity="error",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        fix_suggestion=f"Добавьте docstring для класса {node.name}."
                    )
                )
            self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Анализирует синхронную функцию на наличие docstring.

        Args:
            node: AST-узел определения функции.
        """
        self._check_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Анализирует асинхронную функцию на наличие docstring.

        Args:
            node: AST-узел определения асинхронной функции.
        """
        self._check_func(node)

    def _check_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Игнорируем перегрузки @overload
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "overload":
                return
            if isinstance(dec, ast.Attribute) and dec.attr == "overload":
                return

        is_public = not node.name.startswith("_") or node.name in ("__init__", "__call__")
        if not is_public:
            return

        doc = ast.get_docstring(node)
        if not doc:
            self.issues.append(
                LintResult(
                    rule_name=self.rule_name,
                    message=f"У публичной функции/метода {node.name} отсутствует docstring.",
                    severity="error",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    fix_suggestion=f"Добавьте docstring для {node.name}."
                )
            )
        else:
            # Парсим аргументы из сигнатуры
            args_names: list[str] = []
            for arg in node.args.args:
                if arg.arg not in ("self", "cls"):
                    args_names.append(arg.arg)
            if node.args.kwarg:
                args_names.append(node.args.kwarg.arg)
            if node.args.vararg:
                args_names.append(node.args.vararg.arg)

            if args_names:
                # Проверка наличия раздела аргументов
                if "Args:" not in doc and "Parameters:" not in doc:
                    self.issues.append(
                        LintResult(
                            rule_name=self.rule_name,
                            message=f"Docstring функции {node.name} не содержит раздела аргументов 'Args:'.",
                            severity="warn",
                            file_path=self.file_path,
                            line_number=node.lineno,
                            fix_suggestion="Добавьте раздел 'Args:' в Google Style для описания параметров."
                        )
                    )
                else:
                    # Проверка документированности каждого аргумента
                    for arg_name in args_names:
                        if arg_name not in doc:
                            self.issues.append(
                                LintResult(
                                    rule_name=self.rule_name,
                                    message=f"Параметр '{arg_name}' функции {node.name} не описан в docstring.",
                                    severity="warn",
                                    file_path=self.file_path,
                                    line_number=node.lineno,
                                    fix_suggestion=f"Опишите параметр '{arg_name}' в разделе 'Args:'."
                                )
                            )

            # Проверка Returns: в docstring при непустом возвращаемом типе
            has_return = False
            if node.returns:
                if isinstance(node.returns, ast.Constant) and node.returns.value is None:
                    pass
                elif isinstance(node.returns, ast.Name) and node.returns.id == "None":
                    pass
                else:
                    has_return = True

            if has_return and "Returns:" not in doc and "Yields:" not in doc:
                self.issues.append(
                    LintResult(
                        rule_name=self.rule_name,
                        message=f"Docstring функции {node.name} не содержит раздела возвращаемого значения 'Returns:'.",
                        severity="warn",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        fix_suggestion="Добавьте раздел 'Returns:' в Google Style для описания возвращаемого значения."
                    )
                )

        # Проверка аннотаций типов параметров (всегда, даже без docstring)
        for arg in node.args.args:
            if arg.arg not in ("self", "cls") and not arg.annotation:
                self.issues.append(
                    LintResult(
                        rule_name=self.rule_name,
                        message=f"У параметра '{arg.arg}' функции {node.name} отсутствует аннотация типа.",
                        severity="error",
                        file_path=self.file_path,
                        line_number=arg.lineno,
                        fix_suggestion=f"Добавьте аннотацию типа для '{arg.arg}'."
                    )
                )

        # Проверка аннотации возвращаемого значения (всегда, даже без docstring)
        if node.name != "__init__" and not node.returns:
            self.issues.append(
                LintResult(
                    rule_name=self.rule_name,
                    message=f"У функции {node.name} отсутствует аннотация возвращаемого значения.",
                    severity="error",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    fix_suggestion="Добавьте аннотацию возвращаемого типа (например, -> None)."
                )
            )


class DocstringQualityRule(Rule):
    """
    Правило проверки docstrings по стандарту Google Style и type hints.
    """
    name = "DocstringQualityRule"
    description = "Проверяет наличие/качество docstrings (Google Style) и type hints у публичных классов и методов."
    severity = "error"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет аудит docstrings и аннотаций типов в исходных кодах.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных ошибок форматирования docstrings.
        """
        results: list[LintResult] = []
        for file_path in files:
            if not file_path.endswith(".py"):
                continue
            if "tests" in Path(file_path).parts or "test" in Path(file_path).name.lower() or "setup.py" in Path(
                    file_path).name:
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
                visitor = DocstringVisitor(file_path, self.name)
                visitor.visit(tree)
                results.extend(visitor.issues)
            except Exception:
                pass
        return results


class SecurityHardcodeRule(Rule):
    """
    Правило обнаружения жестко заданных секретов и ключей.
    """
    name = "SecurityHardcodeRule"
    description = "Поиск захардкоженных токенов, паролей и приватных ключей."
    severity = "error"

    SECRET_REGEXES = {
        "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "Private Key Header": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "Slack Token": re.compile(r"xox[bapr]-[0-9]{12}"),
        "Generic Secret": re.compile(
            r"(?:key|secret|password|passwd|token|credential|pwd)\s*=\s*['\"]([a-zA-Z0-9_\-\.\:\/\+\=\%\@]{16,})['\"]",
            re.IGNORECASE
        )
    }

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет поиск жестко заданных паролей и ключей.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных захардкоженных секретов.
        """
        results: list[LintResult] = []
        for file_path in files:
            if file_path.endswith((".pyc", ".png", ".jpg", ".ico", ".zip", ".tar.gz")):
                continue
            if "tests" in Path(file_path).parts or "test" in Path(file_path).name.lower() or "mock" in Path(
                    file_path).name.lower():
                continue

            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            # 1. Текстовое сканирование
            for name, regex in self.SECRET_REGEXES.items():
                for i, line in enumerate(content.splitlines(), 1):
                    if "placeholder" in line.lower() or "your_" in line.lower():
                        continue
                    match = regex.search(line)
                    if match:
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"Обнаружен потенциальный секрет ({name}).",
                                severity=self.severity,
                                file_path=file_path,
                                line_number=i,
                                fix_suggestion="Вынесите секрет в переменные окружения или задействуйте secret_manager."
                            )
                        )

            # 2. AST сканирование (только для .py)
            if file_path.endswith(".py"):
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    var_name = target.id.lower()
                                    if any(k in var_name for k in ("key", "secret", "password", "token", "pwd")):
                                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                            val = node.value.value
                                            if val and len(val) > 8 and not any(
                                                    p in val.lower() for p in
                                                    ("placeholder", "test", "your_", "default", "env", "config", "_key",
                                                     "_token", "_password", "_pwd")
                                            ):
                                                results.append(
                                                    LintResult(
                                                        rule_name=self.name,
                                                        message=f"Обнаружено жестко заданное значение для секретной переменной '{target.id}'.",
                                                        severity=self.severity,
                                                        file_path=file_path,
                                                        line_number=node.lineno,
                                                        fix_suggestion=f"Не храните секреты в кодовой базе. Перенесите '{target.id}' в окружение."
                                                    )
                                                )
                except Exception:
                    pass
        return results


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
        return results


class APIMapRule(Rule):
    """
    Правило валидации карты API (api_map.md) для соответствия текущему экспорту.
    """
    name = "APIMapRule"
    description = "Сверяет api_map.md с реальным кодом (актуально для библиотеки chutils)."
    severity = "error"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет проверку актуальности карты API.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список несовпадений карты API с экспортом chutils.
        """
        results: list[LintResult] = []
        base_path = Path(base_dir)
        api_map_path = base_path / "api_map.md"

        if not (base_path / "src" / "chutils").exists():
            return results

        if not api_map_path.exists():
            results.append(
                LintResult(
                    rule_name=self.name,
                    message="В корне проекта chutils отсутствует файл api_map.md.",
                    severity=self.severity,
                    file_path=str(api_map_path),
                    fix_suggestion="Сгенерируйте карту API: chutils dev generate-context -o api_map.md"
                )
            )
            return results

        try:
            import chutils
            import inspect

            public_attrs = [attr for attr in dir(chutils) if not attr.startswith('_')]
            api_data: list[dict[str, Any]] = []

            for attr_name in public_attrs:
                try:
                    obj = getattr(chutils, attr_name)
                    obj_type = "module"
                    signature = ""
                    doc = inspect.getdoc(obj) or ""

                    if not inspect.isclass(obj) and not inspect.isfunction(obj) and not inspect.ismodule(obj):
                        if isinstance(obj, (bool, int, float, str, type(None))):
                            if doc == inspect.getdoc(type(obj)):
                                doc = ""

                    summary = doc.split('\n')[0] if doc else ""

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

                    signature = re.sub(r' at 0x[0-9a-fA-F]+', '', signature)

                    api_data.append({
                        "name": attr_name,
                        "type": obj_type,
                        "signature": signature,
                        "summary": summary
                    })
                except Exception:
                    pass

            api_data.sort(key=lambda x: x["name"])

            expected_content = "# Public API Map: chutils\n\n"

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

            expected_content += header_line + "\n" + align_line + "\n"
            for row in rows:
                row_line = "|" + "".join(f" {row[i].ljust(col_widths[i])} |" for i in range(len(headers)))
                expected_content += row_line + "\n"

            with open(api_map_path, encoding="utf-8") as f:
                actual_content = f.read()

            if actual_content.strip() != expected_content.strip():
                results.append(
                    LintResult(
                        rule_name=self.name,
                        message="Файл api_map.md устарел или не соответствует экспортируемому API chutils.",
                        severity=self.severity,
                        file_path=str(api_map_path),
                        fix_suggestion="Обновите карту API: chutils dev generate-context -o api_map.md"
                    )
                )
        except Exception as e:
            results.append(
                LintResult(
                    rule_name=self.name,
                    message=f"Ошибка проверки api_map.md: {e}",
                    severity=self.severity,
                    file_path=str(api_map_path)
                )
            )
        return results
