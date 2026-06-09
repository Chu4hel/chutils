"""
Ядро движка проверки AI-готовности (ai-lint).
Определяет базовые классы Rule, LintResult и LinterEngine,
а также набор встроенных правил.
"""

from __future__ import annotations

import ast
import fnmatch
import importlib.util
import os
import re
from pathlib import Path
from typing import Optional, Union, Any

try:
    from pydantic import BaseModel

    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


    class BaseModel:  # type: ignore[no-redef]
        pass

if HAS_PYDANTIC:
    class LintResult(BaseModel):
        """
        Представляет результат одной проверки правила.
        """
        rule_name: str
        message: str
        severity: str
        file_path: Optional[str] = None
        line_number: Optional[int] = None
        fix_suggestion: Optional[str] = None
else:
    class LintResult:  # type: ignore[no-redef]
        """
        Представляет результат одной проверки правила (Fallback версия без Pydantic).
        """

        def __init__(
                self,
                rule_name: str,
                message: str,
                severity: str,
                file_path: Optional[str] = None,
                line_number: Optional[int] = None,
                fix_suggestion: Optional[str] = None,
        ) -> None:
            self.rule_name = rule_name
            self.message = message
            self.severity = severity
            self.file_path = file_path
            self.line_number = line_number
            self.fix_suggestion = fix_suggestion


class Rule:
    """
    Абстрактный базовый класс для всех правил линтера.
    """
    name: str = ""
    description: str = ""
    severity: str = "error"  # Может быть "error" или "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """
        Выполняет проверку правила по списку файлов.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список абсолютных путей к файлам проекта.

        Returns:
            Список объектов LintResult с найденными проблемами.
        """
        raise NotImplementedError("Каждое правило должно реализовывать метод check.")


# --- Встроенные правила ---

class ManifestRule(Rule):
    """
    Правило проверки наличия манифестов для ИИ (antigravity.md, agents.md, GEMINI.md).
    """
    name = "ManifestRule"
    description = "Проверяет наличие файлов манифестов ИИ (antigravity.md, agents.md, GEMINI.md) в ключевых директориях."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
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
        self.file_path = file_path
        self.rule_name = rule_name
        self.issues: list[LintResult] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
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
        self._check_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_func(node)

    def _check_func(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
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
        results: list[LintResult] = []
        for file_path in files:
            if not file_path.endswith(".py"):
                continue
            if "test" in Path(file_path).name.lower() or "setup.py" in Path(file_path).name:
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
            visitor = DocstringVisitor(file_path, self.name)
            visitor.visit(tree)
            results.extend(visitor.issues)
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
        results: list[LintResult] = []
        for file_path in files:
            if file_path.endswith((".pyc", ".png", ".jpg", ".ico", ".zip", ".tar.gz")):
                continue
            if "test" in Path(file_path).name.lower() or "mock" in Path(file_path).name.lower():
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
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
                                                    ("placeholder", "test", "your_", "default", "env", "config")
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
        results: list[LintResult] = []
        for file_path in files:
            if not file_path.endswith(".py"):
                continue
            # Пропускаем сам пакет chutils во избежание рекурсивных предупреждений внутри библиотеки
            if "src/chutils/" in file_path.replace("\\", "/"):
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
            except Exception:
                continue

            for node in ast.walk(tree):
                # Проверка импорта logging/keyring
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
        results: list[LintResult] = []
        base_path = Path(base_dir)
        api_map_path = base_path / "api_map.md"

        # Применяется только если мы находимся внутри проекта chutils
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
            expected_content += "| Name | Type | Signature | Description |\n"
            expected_content += "| :--- | :--- | :--- | :--- |\n"
            for item in api_data:
                sig = f"`{item['signature']}`" if item['signature'] else ""
                expected_content += f"| `{item['name']}` | {item['type']} | {sig} | {item['summary']} |\n"

            with open(api_map_path, "r", encoding="utf-8") as f:
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


def load_custom_rules(custom_rules_path: str) -> list[Rule]:
    """
    Динамически загружает пользовательские правила из указанного файла.

    Args:
        custom_rules_path: Путь к файлу с правилами (например, .chutils/lint_rules.py).

    Returns:
        Список загруженных экземпляров пользовательских правил.
    """
    rules: list[Rule] = []
    path = Path(custom_rules_path)
    if not path.exists():
        return rules

    try:
        spec = importlib.util.spec_from_file_location("custom_lint_rules", str(path))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Находим все классы в модуле, которые наследуют Rule
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Rule) and attr is not Rule:
                    rules.append(attr())
    except Exception:
        # В случае ошибок загрузки возвращаем то, что удалось загрузить
        pass
    return rules


class LinterEngine:
    """
    Движок линтера, координирующий сбор файлов, загрузку правил и их выполнение.
    """

    def __init__(self, config: dict[str, Union[str, bool, list[str], None]]) -> None:
        """
        Инициализирует движок с переданной конфигурацией.

        Args:
            config: Словарь настроек линтера.
        """
        self.config = config
        self.base_dir = Path(str(config.get("base_dir") or os.getcwd())).resolve()

        # Безопасное приведение типов для ignore
        raw_ignore = config.get("ignore")
        if isinstance(raw_ignore, list):
            self.ignore_patterns = [str(item) for item in raw_ignore]
        else:
            self.ignore_patterns = []

        self.strict = bool(config.get("strict", False))
        self.soft_mode = bool(config.get("soft_mode", False))
        self.rules: list[Rule] = []

    def load_rules(self) -> None:
        """
        Загружает правила (встроенные и кастомные).
        """
        # Регистрируем встроенные правила
        self.rules = [
            ManifestRule(),
            DocstringQualityRule(),
            SecurityHardcodeRule(),
            ChutilsIntegrationRule(),
            APIMapRule()
        ]

        # Загружаем кастомные правила
        custom_path = self.config.get("custom_rules_path")
        if isinstance(custom_path, str) and custom_path:
            abs_custom_path = Path(self.base_dir) / custom_path
            if abs_custom_path.exists():
                self.rules.extend(load_custom_rules(str(abs_custom_path)))

    def should_ignore(self, path: Path) -> bool:
        """
        Проверяет, должен ли данный путь быть проигнорирован.

        Args:
            path: Проверяемый путь.

        Returns:
            True, если путь соответствует какому-либо шаблону игнорирования.
        """
        try:
            rel_path = path.relative_to(self.base_dir)
        except ValueError:
            return False

        parts = rel_path.parts
        for pattern in self.ignore_patterns:
            if not pattern:
                continue
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
            if fnmatch.fnmatch(str(rel_path).replace("\\", "/"), pattern):
                return True
            if pattern in str(rel_path).replace("\\", "/"):
                return True
        return False

    def collect_files(self) -> list[str]:
        """
        Собирает все неигнорируемые файлы в проекте.

        Returns:
            Список абсолютных путей к файлам.
        """
        all_files: list[str] = []
        for root, dirs, filenames in os.walk(self.base_dir):
            # Отсекаем игнорируемые директории на месте для оптимизации обхода
            pruned_dirs: list[str] = []
            for d in dirs:
                dir_path = Path(root) / d
                if not self.should_ignore(dir_path):
                    pruned_dirs.append(d)
            dirs[:] = pruned_dirs

            for filename in filenames:
                file_path = Path(root) / filename
                if not self.should_ignore(file_path):
                    all_files.append(str(file_path.resolve()))
        return all_files

    def run(self) -> list[LintResult]:
        """
        Запускает все включенные правила на собранных файлах.

        Returns:
            Список результатов проверок с найденными ошибками и предупреждениями.
        """
        if not self.rules:
            self.load_rules()
        files = self.collect_files()

        results: list[LintResult] = []
        # Фильтруем правила, если в конфигурации явно задан список активных правил
        config_rules = self.config.get("rules")
        enabled_names: list[str] = []
        if isinstance(config_rules, list):
            enabled_names = [str(name) for name in config_rules]

        for rule in self.rules:
            if enabled_names and rule.name not in enabled_names:
                continue

            try:
                rule_results = rule.check(str(self.base_dir), files)
                results.extend(rule_results)
            except Exception as e:
                results.append(
                    LintResult(
                        rule_name=rule.name,
                        message=f"Ошибка при выполнении правила {rule.name}: {str(e)}",
                        severity="error"
                    )
                )
        return results

    def print_results(self, results: list[LintResult]) -> bool:
        """
        Выводит результаты работы линтера в консоль и возвращает статус завершения.

        Args:
            results: Список результатов.

        Returns:
            True, если проверка успешна (нет критических ошибок в строгом режиме/обычном),
            False в противном случае.
        """
        from chutils.cli_utils import get_console
        console = get_console()

        if not results:
            console.print("[green]✓ Все проверки пройдены! Код готов к работе с AI.[/green]")
            return True

        errors_count = 0
        warnings_count = 0

        # Сортируем результаты по путям файлов, критичности и строкам
        sorted_results = sorted(
            results,
            key=lambda r: (r.file_path or "", r.severity, r.line_number or 0)
        )

        for r in sorted_results:
            color = "red" if r.severity == "error" else "yellow"
            severity_str = f"[{color}]{r.severity.upper()}[/{color}]"

            loc_str = ""
            if r.file_path:
                try:
                    rel_file = str(Path(r.file_path).relative_to(self.base_dir))
                except ValueError:
                    rel_file = r.file_path
                loc_str = f"{rel_file}"
                if r.line_number is not None:
                    loc_str += f":{r.line_number}"
                loc_str = f"[cyan]{loc_str}[/cyan]: "

            rule_str = f"[blue][{r.rule_name}][/blue]"
            console.print(f"{loc_str}{severity_str} {rule_str} {r.message}")
            if r.fix_suggestion:
                console.print(f"    [dim]Рекомендация: {r.fix_suggestion}[/dim]")

            if r.severity == "error":
                errors_count += 1
            else:
                warnings_count += 1

        console.rule("Итоги аудита")
        summary_msg = f"Найдено проблем: {len(results)} (Ошибок: {errors_count}, Предупреждений: {warnings_count})"
        if errors_count > 0:
            console.print(f"[red]✗ {summary_msg}[/red]")
        else:
            console.print(f"[yellow]⚠ {summary_msg}[/yellow]")

        if self.soft_mode:
            return True
        if errors_count > 0:
            return False
        if self.strict and warnings_count > 0:
            return False
        return True
