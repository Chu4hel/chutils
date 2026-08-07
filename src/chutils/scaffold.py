"""Распаковщик шаблонов приложений (VK Mini App, VK Bot, etc.)."""

import os
from pathlib import Path
from typing import Any


def unpack_template(template_name: str, target_dir: str | Path, context: dict[str, Any] | None = None) -> list[str]:
    """Распаковывает выбранный шаблон проекта из `chutils.templates` в целевую директорию.

    Args:
        template_name: Имя шаблона ('vk-miniapp', 'vk-bot', 'vk-bot-miniapp').
        target_dir: Путь назначения.
        context: Словарь переменных для подстановки в .template файлах.

    Returns:
        Список созданных файлов.
    """
    target = Path(target_dir)
    context = context or {"project_name": target.name or "App"}

    # Корневой путь шаблонов
    base_templates_dir = Path(__file__).parent / "templates" / "vk" / template_name

    created_files: list[str] = []

    if not base_templates_dir.exists():
        # Если шаблон пустой или не существует, создаем базовую структуру
        target.mkdir(parents=True, exist_ok=True)
        return created_files

    for root, _, files in os.walk(base_templates_dir):
        rel_root = Path(root).relative_to(base_templates_dir)
        dest_dir = target / rel_root
        dest_dir.mkdir(parents=True, exist_ok=True)

        for file_name in files:
            src_file = Path(root) / file_name
            dest_file_name = file_name.removesuffix(".template")
            dest_file = dest_dir / dest_file_name

            content = src_file.read_text(encoding="utf-8")
            for key, val in context.items():
                content = content.replace(f"{{{{ {key} }}}}", str(val))
                content = content.replace(f"{{{{{key}}}}}", str(val))

            dest_file.write_text(content, encoding="utf-8")
            created_files.append(str(dest_file))

    return created_files
