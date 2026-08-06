from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from chutils.dev.models import ProjectIndex, Node


def get_changed_files(project_root: Path) -> list[Path]:
    """Возвращает список измененных или новых Python файлов относительно Git.

    Args:
        project_root: Корень целевого проекта.

    Returns:
        Список путей к изменившимся или созданным .py файлам.
    """
    changed_files: set[Path] = set()

    try:
        # Изменения с последнего коммита (staged + unstaged)
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Формат git status --porcelain: 'XY filename' или 'R  old -> new'
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                continue
            status, path_str = parts[0], parts[1]

            if "->" in path_str:
                path_str = path_str.split("->")[-1].strip()

            path_str = path_str.strip('"\'')
            if path_str.endswith(".py"):
                full_p = (project_root / path_str).resolve()
                changed_files.add(full_p)
    except Exception:
        # Если команда git не сработала или проект не гитовский, возвращаем пустой список
        pass

    return list(changed_files)


def update_tree_incrementally(
    old_index_data: dict[str, Any],
    changed_files: list[Path],
    indexer_class: Any,
    project_root: Path,
    use_gitignore: bool = True,
    custom_ignore: list[str] | None = None,
) -> dict[str, Any]:
    """Обновляет иерархический индекс проекта частичной переиндексацией изменившихся файлов.

    Args:
        old_index_data: Старый словарь Pydantic модели ProjectIndex.
        changed_files: Список путей к изменившимся .py файлам.
        indexer_class: Класс Indexer из ast_indexer.
        project_root: Корневой путь проекта.
        use_gitignore: Флаг учета .gitignore.
        custom_ignore: Список кастомных игноров.

    Returns:
        Обновленный словарь метаданных ProjectIndex.
    """
    if not changed_files:
        return old_index_data

    # Создаем полный свежий индекс для извлечения узлов измененных файлов
    indexer = indexer_class(str(project_root), custom_ignore=custom_ignore, use_gitignore=use_gitignore)
    fresh_index = indexer.index()
    fresh_data = json.loads(fresh_index.model_dump_json())

    changed_rel_paths = {
        p.relative_to(project_root).as_posix()
        for p in changed_files
        if p.exists() and p.is_relative_to(project_root)
    }

    # Вспомогательная функция обновления узла дерева
    def replace_node_recursive(old_node: dict[str, Any], fresh_root: dict[str, Any]) -> dict[str, Any]:
        node_path = old_node.get("path", "")
        if node_path in changed_rel_paths:
            # Находим обновленный узел в свежем дереве
            fresh_node = _find_node_by_path(fresh_root, node_path)
            if fresh_node:
                return fresh_node

        if "children" in old_node and isinstance(old_node["children"], list):
            updated_children = []
            for child in old_node["children"]:
                updated_children.append(replace_node_recursive(child, fresh_root))
            old_node["children"] = updated_children

        return old_node

    updated_root = replace_node_recursive(old_index_data.get("root", {}), fresh_data.get("root", {}))
    old_index_data["root"] = updated_root

    # Обновляем метаданные хэша проекта
    if "metadata" in old_index_data and "metadata" in fresh_data:
        old_index_data["metadata"]["project_hash"] = fresh_data["metadata"].get("project_hash", "")
        old_index_data["metadata"]["generated_at"] = fresh_data["metadata"].get("generated_at", "")

    return old_index_data


def _find_node_by_path(node: dict[str, Any], target_path: str) -> dict[str, Any] | None:
    """Ищет узел в дереве по его относительному пути."""
    if node.get("path") == target_path:
        return node
    for child in node.get("children", []):
        res = _find_node_by_path(child, target_path)
        if res:
            return res
    return None
