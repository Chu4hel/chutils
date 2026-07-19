from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

from ..ai_lint import Rule, LintResult
from ..project_metadata import calculate_project_hash


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

        # Если включен режим staged, проверяем, изменились ли Python-файлы.
        # Если изменений нет, пропускаем проверку.
        if getattr(self, "staged", False):
            if not any(f.endswith(".py") for f in files):
                return results

        targets = []
        cache_path = base_path / ".chutils" / "context_metadata.json"
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    cache_data = json.load(f)
                if "files" in cache_data and isinstance(cache_data["files"], dict):
                    # Новый многофайловый формат
                    for file_rel, file_meta in cache_data["files"].items():
                        t_path = base_path / file_rel
                        t_format = file_meta.get("format", "markdown")
                        targets.append((t_path, t_format))
                elif "file_path" in cache_data:
                    # Старый однофайловый формат (обратная совместимость)
                    file_rel = cache_data.get("file_path")
                    if file_rel:
                        t_path = base_path / file_rel
                        t_format = cache_data.get("format", "markdown")
                        targets.append((t_path, t_format))
            except Exception:
                pass

        if not targets:
            for fname, fmt in [("api_map.md", "markdown"), ("project_index.json", "tree"),
                               ("project_tree.json", "tree")]:
                p = base_path / fname
                if p.exists():
                    targets.append((p, fmt))

        if not targets:
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

            for target_file_path, target_format in targets:
                if not target_file_path.exists():
                    if cache_path.exists():
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"Файл контекста не найден: {target_file_path.name}",
                                severity=self.severity,
                                file_path=str(target_file_path),
                                fix_suggestion=f"Сгенерируйте контекст: chutils dev generate-context -o {target_file_path.name}"
                            )
                        )
                    continue

                if target_format == "markdown":
                    expected_content = "# Public API Map: chutils\n\n"

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

                    expected_content += header_line + "\n" + align_line + "\n"
                    for row in rows:
                        row_line = "|" + "".join(f" {row[i].ljust(col_widths[i])} |" for i in range(len(headers)))
                        expected_content += row_line + "\n"

                    try:
                        with open(target_file_path, encoding="utf-8") as f:
                            actual_content = f.read()
                    except Exception:
                        continue

                    actual_compare = actual_content.strip()
                    if actual_compare.startswith("---"):
                        parts = actual_compare.split("---", 2)
                        if len(parts) >= 3:
                            actual_compare = parts[2].strip()

                    if actual_compare != expected_content.strip():
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"Файл {target_file_path.name} устарел или не соответствует экспортируемому API chutils.",
                                severity=self.severity,
                                file_path=str(target_file_path),
                                fix_suggestion=f"Обновите карту API: chutils dev generate-context -o {target_file_path.name}"
                            )
                        )
                elif target_format == "json":
                    try:
                        with open(target_file_path, encoding="utf-8") as f:
                            actual_data = json.load(f)
                    except Exception:
                        continue

                    actual_api = actual_data.get("api", []) if isinstance(actual_data, dict) else actual_data
                    expected_api = []
                    for item in api_data:
                        expected_api.append({
                            "name": item["name"],
                            "type": item["type"],
                            "signature": item["signature"],
                            "summary": item["summary"]
                        })

                    mismatch = False
                    if len(actual_api) != len(expected_api):
                        mismatch = True
                    else:
                        for a, e in zip(actual_api, expected_api):
                            if (a.get("name") != e["name"] or
                                    a.get("type") != e["type"] or
                                    a.get("signature") != e["signature"]):
                                mismatch = True
                                break

                    if mismatch:
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"Файл контекста ({target_file_path.name}) устарел или не соответствует текущему экспорту API.",
                                severity=self.severity,
                                file_path=str(target_file_path),
                                fix_suggestion=f"Обновите контекст: chutils dev generate-context -f json -o {target_file_path.name}"
                            )
                        )
                elif target_format == "tree":
                    try:
                        from chutils.dev.ast_indexer import Indexer
                        scan_path = base_path / "src" / "chutils"
                        indexer = Indexer(str(scan_path))
                        expected_index = indexer.index()
                    except Exception:
                        continue

                    with open(target_file_path, encoding="utf-8") as f:
                        actual_data = json.load(f)

                    expected_dump = expected_index.model_dump()
                    mismatch = False
                    if "root" not in actual_data or "dependency_graph" not in actual_data:
                        mismatch = True
                    else:
                        if actual_data.get("root") != expected_dump.get("root") or actual_data.get(
                                "dependency_graph") != expected_dump.get("dependency_graph"):
                            mismatch = True

                    if mismatch:
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"Иерархический индекс ({target_file_path.name}) устарел или не соответствует структуре проекта.",
                                severity=self.severity,
                                file_path=str(target_file_path),
                                fix_suggestion=f"Обновите индекс: chutils dev generate-context --tree -o {target_file_path.name}"
                            )
                        )

        except Exception as e:
            results.append(
                LintResult(
                    rule_name=self.name,
                    message=f"Ошибка проверки: {e}",
                    severity=self.severity,
                    file_path=str(base_path)
                )
            )
        return results


class APIMapHashRule(Rule):
    """
    Правило валидации хэша проекта по карте API.
    """
    name = "APIMapHashRule"
    description = "Сверяет текущий SHA-256 хэш проекта с хэшем, записанным в api_map.md."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет сверку хэша проекта.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных расхождений хэша.
        """
        results: list[LintResult] = []
        base_path = Path(base_dir)

        if not (base_path / "src" / "chutils").exists():
            return results

        # Если включен режим staged, проверяем, изменились ли Python-файлы.
        # Если изменений нет, пропускаем проверку.
        if getattr(self, "staged", False):
            if not any(f.endswith(".py") for f in files):
                return results

        targets = []
        cache_path = base_path / ".chutils" / "context_metadata.json"
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    cache_data = json.load(f)
                if "files" in cache_data and isinstance(cache_data["files"], dict):
                    # Новый многофайловый формат
                    for file_rel, file_meta in cache_data["files"].items():
                        t_path = base_path / file_rel
                        t_format = file_meta.get("format", "markdown")
                        t_hash = file_meta.get("project_hash")
                        targets.append((t_path, t_format, t_hash))
                elif "file_path" in cache_data:
                    # Старый однофайловый формат (обратная совместимость)
                    file_rel = cache_data.get("file_path")
                    if file_rel:
                        t_path = base_path / file_rel
                        t_format = cache_data.get("format", "markdown")
                        t_hash = cache_data.get("project_hash")
                        targets.append((t_path, t_format, t_hash))
            except Exception:
                pass

        if not targets:
            for fname, fmt in [("api_map.md", "markdown"), ("project_index.json", "tree"),
                               ("project_tree.json", "tree")]:
                p = base_path / fname
                if p.exists():
                    targets.append((p, fmt, None))

        if not targets:
            return results

        actual_hash = calculate_project_hash(base_path)

        for target_file_path, target_format, expected_hash in targets:
            if not target_file_path.exists():
                if cache_path.exists():
                    results.append(
                        LintResult(
                            rule_name=self.name,
                            message=f"Файл контекста не найден: {target_file_path.name}",
                            severity=self.severity,
                            file_path=str(target_file_path),
                            fix_suggestion=f"Сгенерируйте контекст: chutils dev generate-context -o {target_file_path.name}"
                        )
                    )
                continue

            project_hash = None
            if target_format == "markdown":
                try:
                    with open(target_file_path, encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue

                # Парсим Frontmatter
                lines = content.splitlines()
                if not lines or lines[0].strip() != "---":
                    results.append(
                        LintResult(
                            rule_name=self.name,
                            message=f"В {target_file_path.name} отсутствует блок метаданных (YAML Frontmatter).",
                            severity=self.severity,
                            file_path=str(target_file_path),
                            fix_suggestion=f"Перегенерируйте карту API: chutils dev generate-context -o {target_file_path.name}"
                        )
                    )
                    continue

                frontmatter_lines = []
                found_end = False
                for line in lines[1:]:
                    if line.strip() == "---":
                        found_end = True
                        break
                    frontmatter_lines.append(line)

                if not found_end:
                    results.append(
                        LintResult(
                            rule_name=self.name,
                            message=f"Блок метаданных (YAML Frontmatter) в {target_file_path.name} не закрыт.",
                            severity=self.severity,
                            file_path=str(target_file_path),
                            fix_suggestion=f"Перегенерируйте карту API: chutils dev generate-context -o {target_file_path.name}"
                        )
                    )
                    continue

                for line in frontmatter_lines:
                    if ":" in line:
                        key, val = line.split(":", 1)
                        if key.strip() == "project_hash":
                            project_hash = val.strip()
                            break
            else:
                # json или tree
                try:
                    with open(target_file_path, encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        project_hash = data.get("metadata", {}).get("project_hash")
                except Exception:
                    pass

            if not project_hash:
                project_hash = expected_hash

            if not project_hash:
                results.append(
                    LintResult(
                        rule_name=self.name,
                        message=f"В метаданных {target_file_path.name} отсутствует хэш проекта (project_hash).",
                        severity=self.severity,
                        file_path=str(target_file_path),
                        fix_suggestion=f"Перегенерируйте карту API: chutils dev generate-context -o {target_file_path.name}"
                    )
                )
                continue

            if actual_hash != project_hash:
                cmd_suggestion = f"chutils dev generate-context -o {target_file_path.name}"
                if target_format == "tree":
                    cmd_suggestion = f"chutils dev generate-context --tree -o {target_file_path.name}"
                elif target_format == "json":
                    cmd_suggestion = f"chutils dev generate-context -f json -o {target_file_path.name}"

                results.append(
                    LintResult(
                        rule_name=self.name,
                        message=f"Файл контекста ({target_file_path.name}) устарел: хэш проекта изменился.",
                        severity=self.severity,
                        file_path=str(target_file_path),
                        fix_suggestion=f"Обновите контекст: {cmd_suggestion}"
                    )
                )

        return results
