"""Интерактивный регистратор действий в браузере с инъекцией HUD и генерацией отчетов по DOM."""

from __future__ import annotations

import asyncio
import json
import logging  # chutils: ignore[ChutilsIntegrationRule]
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from chutils.fs import atomic_write, ensure_dir
from chutils.time import utc_now

from .dom_models import (
    DOMActionSessionReport,
    RecordedAction,
    RecordedChecklistItem,
    ViewportInfo,
)
from .dom_scripts import (
    POLL_RECORDED_ACTIONS_SCRIPT,
    build_inject_recorder_hud_script,
)

logger = logging.getLogger(__name__)


def _safe_extract_dict(val: Any) -> dict[str, Any]:
    """Безопасно распаковывает результат вызова evaluate в Python-словарь.

    Args:
        val: Сырой результат выполнения JS в браузере (JSON-строка, dict или пары).

    Returns:
        Словарь с извлеченными полями.
    """
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    if isinstance(val, list):
        res: dict[str, Any] = {}
        for item in val:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                k, v = item
                if isinstance(k, str):
                    if isinstance(v, dict) and "value" in v:
                        res[k] = v["value"]
                    else:
                        res[k] = v
            elif isinstance(item, dict) and "name" in item and "value" in item:
                res[str(item["name"])] = item["value"]
        return res
    return {}


class DOMActionRecorder:
    """Интерактивный регистратор действий пользователя в браузере с плавающим HUD.

    Позволяет визуально размечать шаги сценариев на живых веб-страницах,
    проверять селекторы, отслеживать мутации DOM и формировать подробные
    структурированные отчеты для нейроагентов и тестов.
    """

    def __init__(
        self,
        checklist_items: Sequence[dict[str, Any] | RecordedChecklistItem] | None = None,
        widget_title: str = "Запись действий DOM",
        container_selectors: list[str] | None = None,
        custom_matcher_js: str | None = None,
    ) -> None:
        """Инициализация регистратора.

        Args:
            checklist_items: Список пунктов чеклиста с id, label, hints.
            widget_title: Заголовок, отображаемый в шапке HUD-виджета.
            container_selectors: Дополнительные селекторы модальных окон/панелей.
            custom_matcher_js: Кастомный JS-код функции сопоставления с чеклистом.
        """
        self.widget_title = widget_title
        self.container_selectors = container_selectors or []
        self.custom_matcher_js = custom_matcher_js
        self.checklist_items: list[dict[str, Any]] = []

        if checklist_items:
            for item in checklist_items:
                if isinstance(item, RecordedChecklistItem):
                    self.checklist_items.append(item.model_dump())
                elif isinstance(item, dict):
                    self.checklist_items.append(dict(item))

    async def inject(self, tab: Any) -> bool:
        """Внедряет перехватчик действий и плавающий HUD в страницу браузера.

        Args:
            tab: Объект вкладки браузера (nodriver Tab, Playwright Page или аналогичный
                с асинхронным методом `evaluate`).

        Returns:
            True, если скрипт успешно выполнен.
        """
        script = build_inject_recorder_hud_script(
            checklist=self.checklist_items,
            widget_title=self.widget_title,
            container_selectors=self.container_selectors,
            custom_matcher_js=self.custom_matcher_js,
        )
        try:
            val = await tab.evaluate(script)
            logger.debug("DOM Action Recorder HUD успешно внедрен в страницу.")
            return bool(val)
        except Exception as exc:
            logger.error("Ошибка внедрения DOM Action Recorder HUD: %s", exc)
            return False

    async def poll(self, tab: Any) -> dict[str, Any]:
        """Опрашивает текущий лог действий и состояние HUD из браузера.

        Args:
            tab: Вкладка браузера с методом `evaluate`.

        Returns:
            Словарь с зафиксированными действиями, состоянием чеклиста и вьюпорта.
        """
        try:
            raw_res = await tab.evaluate(POLL_RECORDED_ACTIONS_SCRIPT)
            return _safe_extract_dict(raw_res)
        except Exception as exc:
            logger.debug("Ошибка опроса состояния действий браузера: %s", exc)
            return {}

    async def is_finished(self, tab: Any) -> bool:
        """Проверяет, нажал ли пользователь кнопку завершения в HUD виджете.

        Args:
            tab: Вкладка браузера.

        Returns:
            True, если сессия завершена.
        """
        data = await self.poll(tab)
        return bool(data.get("finished", False))

    def build_report(
        self,
        raw_data: dict[str, Any],
        session_name: str = "default",
        target_name: str = "web",
    ) -> DOMActionSessionReport:
        """Преобразует сырые данные из браузера в типизированный отчет DOMActionSessionReport.

        Args:
            raw_data: Сырой словарь, возвращенный методом `poll()`.
            session_name: Название сессии или имя профиля браузера.
            target_name: Название целевой веб-системы или сайта.

        Returns:
            Структурированный Pydantic-объект отчета.
        """
        actions_raw = raw_data.get("actions", [])
        checklist_raw = raw_data.get("checklist", [])

        actions = [RecordedAction(**a) for a in actions_raw]
        checklist = [RecordedChecklistItem(**c) for c in checklist_raw]

        discovered: dict[str, list[str]] = {}
        for a in actions:
            cat = a.matched_checklist_id or "other_action"
            discovered.setdefault(cat, [])
            if a.computed_selector not in discovered[cat]:
                discovered[cat].append(a.computed_selector)

        session_vp = raw_data.get("session_viewport")
        viewport_obj = ViewportInfo(**session_vp) if session_vp and isinstance(session_vp, dict) else None

        report = DOMActionSessionReport(
            timestamp=utc_now().isoformat(timespec="seconds"),
            session_name=session_name,
            target_name=target_name,
            page_url=raw_data.get("page_url", ""),
            page_title=raw_data.get("page_title", ""),
            total_actions=len(actions),
            session_viewport=viewport_obj,
            actions=actions,
            checklist=checklist,
            discovered_selectors=discovered,
        )
        report.summary_markdown = self.generate_markdown_report(report)
        return report

    def generate_markdown_report(self, report: DOMActionSessionReport) -> str:
        """Формирует подробный Markdown-отчет для чтения разработчиками и LLM-агентами.

        Args:
            report: Объект отчета DOMActionSessionReport.

        Returns:
            Строка в формате Markdown.
        """
        target_label = report.target_name.upper()
        lines: list[str] = [
            f"# 🎥 Отчет записи интерактивных действий DOM ({target_label})",
            "",
            f"- **Цель / Сервис:** `{report.target_name}`",
            f"- **Дата и время:** `{report.timestamp}`",
            f"- **Сессия:** `{report.session_name}`",
            f"- **Страница:** [{report.page_title or 'Без заголовка'}]({report.page_url or 'about:blank'})",
            f"- **Всего зафиксировано действий:** {report.total_actions}",
        ]

        if report.session_viewport:
            vp = report.session_viewport
            lines.append(
                f"- **Разрешение экрана (Viewport):** `{vp.width}x{vp.height}` (DPR: {vp.device_pixel_ratio}, брейкпоинт: `{vp.breakpoint}`)"
            )

        if report.checklist:
            lines.extend([
                "",
                "---",
                "",
                "## 📋 Статус выполнения чеклиста",
                "",
                "| Пункт | Описание и ориентиры | Статус | Селектор элемента |",
                "|---|---|:---:|---|",
            ])

            for item in report.checklist:
                if item.completed:
                    status_ico = "👌 Выполнено (руч.)" if item.is_manual else "✅ Выполнено (auto)"
                else:
                    status_ico = "❌ Пропущено"

                hints_str = f"<br><i>Ориентиры: {', '.join(item.hints)}</i>" if item.hints else ""
                desc_cell = f"{item.description}{hints_str}"
                sel = f"`{item.target_selector}`" if item.target_selector else "—"
                lines.append(f"| {item.label} | {desc_cell} | {status_ico} | {sel} |")

        duplicate_actions = [a for a in report.actions if a.has_duplicates]
        if duplicate_actions:
            lines.extend([
                "",
                "---",
                "",
                "## ⚠️ Предупреждения: Обнаружены селекторы с дубликатами в DOM",
                "",
                "> [!WARNING]",
                "> Следующие селекторы при клике находили более 1 элемента в дереве DOM. В SPA-приложениях это может приводить к кликам по скрытым элементам. Рекомендуется использовать `scoped_selector`!",
                "",
                "| Шаг | Событие | Селектор | Совпадений | Контекст контейнера | Рекомендуемый составной селектор |",
                "|:---:|---|---|:---:|---|---|",
            ])
            for da in duplicate_actions:
                scope_str = f"`{da.container_scope}`" if da.container_scope else "—"
                scoped_str = f"`{da.scoped_selector}`" if da.scoped_selector else f"`{da.computed_selector}`"
                lines.append(
                    f"| {da.action_id} | `{da.event_type}` | `{da.computed_selector}` | **{da.duplicate_count}** | {scope_str} | {scoped_str} |"
                )

        if report.discovered_selectors:
            lines.extend([
                "",
                "---",
                "",
                "## 🎯 Сводка обнаруженных селекторов по категориям",
                "",
            ])
            for cat, selectors in report.discovered_selectors.items():
                lines.append(f"### Категория: `{cat}`")
                for s in selectors:
                    lines.append(f"- Селектор: `{s}`")
                lines.append("")

        lines.extend([
            "---",
            "",
            "## 📜 Хронология выполненных действий пользователя",
            "",
        ])

        if not report.actions:
            lines.append("*Действий не зафиксировано.*")
        else:
            for a in report.actions:
                checklist_tag = f" `[{a.matched_checklist_id}]`" if a.matched_checklist_id else ""
                lines.append(
                    f"### Шаг {a.action_id}: `{a.event_type.upper()}` на `<{a.tag_name}>` (+{a.elapsed_seconds}с){checklist_tag}"
                )
                if a.aria_label:
                    lines.append(f"- **Aria-label:** `{a.aria_label}`")
                if a.role:
                    lines.append(f"- **Role:** `{a.role}`")
                if a.class_names:
                    lines.append(f"- **Classes:** `{a.class_names}`")
                if a.text_snippet:
                    lines.append(f"- **Текст элемента:** `{a.text_snippet}`")
                if a.value_snippet:
                    lines.append(f"- **Введенное значение:** `{a.value_snippet}`")

                lines.append(f"- **Рекомендуемый селектор:** `{a.computed_selector}`")
                if a.container_scope:
                    lines.append(f"- **Контейнер / Оверлей:** `{a.container_scope}`")
                if a.scoped_selector and a.scoped_selector != a.computed_selector:
                    lines.append(f"- **Составной селектор (Scoped):** `{a.scoped_selector}`")
                if a.has_duplicates:
                    lines.append(f"- **Внимание (Дубликаты):** ⚠️ Найдено {a.duplicate_count} совпадений в DOM на момент взаимодействия!")

                if a.alternative_selectors:
                    alts_str = ", ".join(f"`{s}`" for s in a.alternative_selectors)
                    lines.append(f"- **Альтернативные селекторы:** {alts_str}")

                if a.mutation_diff:
                    if a.mutation_diff.spawned_containers:
                        conts = ", ".join(f"`{c}`" for c in a.mutation_diff.spawned_containers)
                        lines.append(f"- **Появившиеся оверлеи/контейнеры:** {conts}")
                    if a.mutation_diff.appeared_elements:
                        elems = ", ".join(f"`{e}`" for e in a.mutation_diff.appeared_elements[:4])
                        lines.append(f"- **Смонтированные интерактивные элементы:** {elems}")

                if a.mutations:
                    lines.append("- **Реакция DOM (мутации):**")
                    for m in a.mutations:
                        lines.append(f"  - `{m}`")

                if a.outer_html:
                    lines.append(f"```html\n{a.outer_html}\n```")
                lines.append("")

        return "\n".join(lines)

    def export_report(
        self,
        report: DOMActionSessionReport,
        json_path: Path,
        md_path: Path | None = None,
    ) -> tuple[Path, Path | None]:
        """Экспортирует структурированный отчет в JSON и Markdown.

        Args:
            report: Объект отчета DOMActionSessionReport.
            json_path: Путь к целевому файлу JSON.
            md_path: Путь к целевому файлу Markdown (по умолчанию .md рядом с JSON).

        Returns:
            Кортеж (путь к JSON, путь к Markdown).
        """
        ensure_dir(json_path.parent)
        json_content = report.model_dump_json(indent=2)
        atomic_write(json_path, json_content)
        logger.info("Отчет сессии записи сохранен в JSON: %s", json_path)

        target_md = md_path or json_path.with_suffix(".md")
        ensure_dir(target_md.parent)
        atomic_write(target_md, report.summary_markdown)
        logger.info("Markdown-отчет сессии сохранен: %s", target_md)

        return json_path, target_md

    async def wait_for_finish(
        self,
        tab: Any,
        poll_interval: float = 0.5,
        timeout: float | None = None,
        on_action: Callable[[RecordedAction], None] | None = None,
        session_name: str = "default",
        target_name: str = "web",
    ) -> DOMActionSessionReport:
        """Асинхронно ожидает нажатия кнопки завершения в HUD виджете браузера.

        Args:
            tab: Вкладка браузера.
            poll_interval: Интервал опроса в секундах.
            timeout: Максимальное время ожидания в секундах (None для неограниченного).
            on_action: Опциональный колбэк при фиксации нового действия.
            session_name: Имя сессии для итогового отчета.
            target_name: Имя цели для итогового отчета.

        Returns:
            Итоговый объект отчета DOMActionSessionReport.

        Raises:
            asyncio.TimeoutError: При истечении таймаута до завершения пользователем.
        """
        start_time = asyncio.get_running_loop().time()
        seen_action_ids: set[int] = set()

        while True:
            if timeout is not None:
                elapsed = asyncio.get_running_loop().time() - start_time
                if elapsed > timeout:
                    raise asyncio.TimeoutError(f"Превышен таймаут ожидания записи ({timeout}с)")

            data = await self.poll(tab)
            if on_action and "actions" in data:
                for a_raw in data["actions"]:
                    a_id = a_raw.get("action_id", 0)
                    if a_id not in seen_action_ids:
                        seen_action_ids.add(a_id)
                        try:
                            action_obj = RecordedAction(**a_raw)
                            on_action(action_obj)
                        except Exception as exc:
                            logger.debug("Ошибка в on_action колбэке: %s", exc)

            if data.get("finished", False):
                return self.build_report(data, session_name=session_name, target_name=target_name)

            await asyncio.sleep(poll_interval)


DOMActionRecorderHUD = DOMActionRecorder
"""Алиас для DOMActionRecorder."""

__all__ = [
    "DOMActionRecorder",
    "DOMActionRecorderHUD",
]
