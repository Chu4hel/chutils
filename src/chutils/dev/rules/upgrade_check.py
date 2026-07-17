"""
Правило проверки обновлений версии пакета chutils и генерации AI-Changelog.
"""
from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
from pathlib import Path

from ..ai_lint import Rule, LintResult
from ..changelog_parser import (
    filter_releases_by_version_range,
    parse_release_body,
    generate_migration_context_markdown,
)
from ..upgrade_client import fetch_changelogs
from ..version_detector import detect_version_upgrade

logger = logging.getLogger("chutils.rules.upgrade_check")


class UpgradeCheckRule(Rule):
    """
    Правило для проверки обновления версии chutils и автоматической генерации AI-Changelog.
    """
    name = "UpgradeCheckRule"
    description = "Обнаруживает обновление версии пакета в pyproject.toml и генерирует миграционный файл контекста для ИИ."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет проверку обновления версии и генерирует AI-Changelog.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных предупреждений (пустой, если версия не изменилась).
        """
        results: list[LintResult] = []

        # 1. Проверяем, изменилась ли версия пакета
        old_version, new_version, is_upgraded = detect_version_upgrade(base_dir)
        if not is_upgraded or not old_version or not new_version:
            return results

        # 2. Получаем чейнджлоги по сети / из кэша
        all_releases = fetch_changelogs(base_dir)
        if not all_releases:
            logger.warning("Не удалось получить информацию о релизах для генерации AI-Changelog.")
            return results

        # 3. Фильтруем релизы в нужном диапазоне
        target_releases = filter_releases_by_version_range(all_releases, old_version, new_version)
        if not target_releases:
            return results

        # 4. Собираем и парсим изменения
        aggregated_changes: dict[str, list[str]] = {
            "breaking_changes": [],
            "new_api": [],
            "deprecations": [],
        }

        for release in target_releases:
            body = release.get("body") or ""
            parsed = parse_release_body(body)
            aggregated_changes["breaking_changes"].extend(parsed["breaking_changes"])
            aggregated_changes["new_api"].extend(parsed["new_api"])
            aggregated_changes["deprecations"].extend(parsed["deprecations"])

        # 5. Генерируем Markdown и пишем в файл .chutils/migration_context.md
        markdown_content = generate_migration_context_markdown(
            aggregated_changes, old_version, new_version
        )

        try:
            from chutils.fs import ensure_dir, atomic_write
            context_file = Path(base_dir) / ".chutils" / "migration_context.md"
            ensure_dir(context_file.parent)
            atomic_write(context_file, markdown_content)
        except Exception as e:
            logger.error("Не удалось записать файл миграционного контекста для ИИ: %s", e)
            return results

        # 6. Формируем красивое предупреждение в линтер
        breaking_count = len(aggregated_changes["breaking_changes"])
        new_api_count = len(aggregated_changes["new_api"])
        deprecations_count = len(aggregated_changes["deprecations"])

        msg_parts = [
            f"Обнаружено обновление версии chutils: v{old_version} -> v{new_version}.",
            "Файл AI-миграции сохранен в .chutils/migration_context.md.",
            "Краткая сводка изменений:",
        ]

        if breaking_count > 0:
            msg_parts.append(f"  - Breaking Changes: {breaking_count} шт.")
        if new_api_count > 0:
            msg_parts.append(f"  - New API: {new_api_count} шт.")
        if deprecations_count > 0:
            msg_parts.append(f"  - Deprecations: {deprecations_count} шт.")

        if breaking_count == 0 and new_api_count == 0 and deprecations_count == 0:
            msg_parts.append("  - Изменений API не обнаружено (патч-обновление или пустой чейнджлог).")

        results.append(
            LintResult(
                rule_name=self.name,
                message="\n".join(msg_parts),
                severity=self.severity,
                file_path=str(Path(base_dir) / "pyproject.toml"),
                fix_suggestion="Ознакомьтесь с файлом .chutils/migration_context.md для получения полной информации по миграции."
            )
        )

        return results
