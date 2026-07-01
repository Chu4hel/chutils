from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def _evaluate_node(node: ast.AST) -> Any:
    """
    Безопасно вычисляет значение простого AST-узла (литерала).
    Возбуждает ValueError, если узел слишком сложный для статического анализа.
    """
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.List):
        return [_evaluate_node(el) for el in node.elts]
    elif isinstance(node, ast.Tuple):
        return tuple(_evaluate_node(el) for el in node.elts)
    elif isinstance(node, ast.Dict):
        res = {}
        for k, v in zip(node.keys, node.values):
            if k is not None:
                eval_k = _evaluate_node(k)
                res[eval_k] = _evaluate_node(v)
        return res
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        val = _evaluate_node(node.operand)
        if isinstance(val, (int, float)):
            return val if isinstance(node.op, ast.UAdd) else -val
    raise ValueError("Node too complex")


def parse_fallbacks_from_file(file_path: str) -> dict[str, dict[str, Any]]:
    """
    Парсит один Python-файл и извлекает значения fallback из вызовов get_config_*.
    """
    fallbacks: dict[str, dict[str, Any]] = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
    except Exception:
        return fallbacks

    class FallbackVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in {
                "get_config_value", "get_config_int", "get_config_float",
                "get_config_boolean", "get_config_list", "get_config_section",
                "get_config_path"
            }:
                try:
                    # Извлекаем section
                    section_node = None
                    if len(node.args) >= 1:
                        section_node = node.args[0]
                    else:
                        for kw in node.keywords:
                            if kw.arg == "section":
                                section_node = kw.value
                                break

                    # Извлекаем key
                    key_node = None
                    if len(node.args) >= 2:
                        key_node = node.args[1]
                    else:
                        for kw in node.keywords:
                            if kw.arg == "key":
                                key_node = kw.value
                                break

                    if section_node is not None and key_node is not None:
                        section = _evaluate_node(section_node)
                        key = _evaluate_node(key_node)

                        if isinstance(section, str) and isinstance(key, str):
                            # Извлекаем fallback
                            fallback_node = None
                            for kw in node.keywords:
                                if kw.arg == "fallback":
                                    fallback_node = kw.value
                                    break
                            if fallback_node is None and len(node.args) >= 3:
                                fallback_node = node.args[2]

                            if fallback_node is not None:
                                fallback_val = _evaluate_node(fallback_node)
                                if section not in fallbacks:
                                    fallbacks[section] = {}
                                fallbacks[section][key] = fallback_val
                except ValueError:
                    pass
                except Exception:
                    pass

            self.generic_visit(node)

    visitor = FallbackVisitor()
    visitor.visit(tree)
    return fallbacks


def parse_fallbacks_from_project(base_dir: str) -> dict[str, dict[str, Any]]:
    """
    Рекурсивно обходит директорию проекта и собирает все дефолтные fallback значения.
    """
    project_fallbacks: dict[str, dict[str, Any]] = {}
    base_path = Path(base_dir)
    if not base_path.exists():
        return project_fallbacks

    for path in base_path.rglob("*.py"):
        parts = path.parts
        # Игнорируем виртуальные окружения, тесты и скрытые папки
        if any(
                p.startswith(".") or p in {
                    "venv", ".venv", "tests", "site-packages",
                    "node_modules", "dist", "build"
                } for p in parts
        ):
            continue

        file_fallbacks = parse_fallbacks_from_file(str(path))
        for section, keys in file_fallbacks.items():
            if section not in project_fallbacks:
                project_fallbacks[section] = {}
            for key, val in keys.items():
                project_fallbacks[section][key] = val

    return project_fallbacks
