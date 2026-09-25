"""Тесты интерактивного регистратора действий DOM, моделей и JavaScript-скриптов."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from chutils import (
    DOMActionRecorder,
    DOMActionRecorderHUD,
    DOMActionSessionReport,
    RecordedAction,
    RecordedChecklistItem,
)
from chutils.scraping.testing.dom_models import (
    DOMMutationDiff,
    ViewportInfo,
)
from chutils.scraping.testing.dom_scripts import (
    CORE_DOM_HELPERS_JS,
    PAGE_META_SCRIPT,
    POLL_RECORDED_ACTIONS_SCRIPT,
    build_inject_recorder_hud_script,
    build_scan_selectors_script,
    get_recorder_hud_ui_js,
)
from chutils.scraping.testing.recorder import _safe_extract_dict


class FakeTab:
    """Мок-вкладка браузера для тестирования асинхронных вызовов evaluate."""

    def __init__(self, eval_return_value: Any = None) -> None:
        self.eval_return_value = eval_return_value
        self.executed_scripts: list[str] = []

    async def evaluate(self, script: str) -> Any:
        self.executed_scripts.append(script)
        if callable(self.eval_return_value):
            return self.eval_return_value(script)
        return self.eval_return_value


def test_dom_models_creation() -> None:
    """Проверяет создание и валидацию Pydantic моделей DOM."""
    vp = ViewportInfo(width=1920, height=1080, device_pixel_ratio=1.5, breakpoint="desktop_wide")
    assert vp.width == 1920
    assert vp.breakpoint == "desktop_wide"

    diff = DOMMutationDiff(
        spawned_containers=[".modal-dialog"],
        appeared_elements=["button.submit"],
        attribute_changes=["~ attr disabled на <button>"],
    )
    assert len(diff.spawned_containers) == 1

    item = RecordedChecklistItem(
        id="step_1",
        label="Клик по кнопке",
        description="Тестовый шаг",
        hints=["button.btn-primary"],
    )
    assert not item.completed
    assert item.target_selector is None

    action = RecordedAction(
        action_id=1,
        event_type="click",
        timestamp="2026-09-25T12:00:00Z",
        elapsed_seconds=1.25,
        tag_name="button",
        computed_selector="button.btn-primary",
        has_duplicates=True,
        duplicate_count=2,
        mutation_diff=diff,
    )
    assert action.action_id == 1
    assert action.has_duplicates
    assert action.duplicate_count == 2


def test_dom_scripts_generation() -> None:
    """Проверяет генерацию JavaScript-скриптов и полифилов."""
    assert "function isElementVisible" in CORE_DOM_HELPERS_JS
    assert "function queryAllSafe" in CORE_DOM_HELPERS_JS
    assert ":contains" in CORE_DOM_HELPERS_JS
    assert ":has-text" in CORE_DOM_HELPERS_JS
    assert "ready_state" in PAGE_META_SCRIPT
    assert "actions_count" in POLL_RECORDED_ACTIONS_SCRIPT

    hud_ui_js = get_recorder_hud_ui_js()
    assert "renderChecklist" in hud_ui_js
    assert "createHud" in hud_ui_js
    assert "updateHudDisplay" in hud_ui_js

    inject_script = build_inject_recorder_hud_script(
        checklist=[
            {"id": "c1", "label": "Тест 1", "hints": ["#btn1"]},
            RecordedChecklistItem(id="c2", label="Тест 2", hints=["#btn2"]),
        ],
        widget_title="Тестовый виджет",
        container_selectors=[".custom-panel"],
    )
    assert "window.__chutilsRecorderInstalled" in inject_script
    assert "Тестовый виджет" in inject_script
    assert ".custom-panel" in inject_script
    assert "MutationObserver" in inject_script

    scan_script = build_scan_selectors_script({
        "buttons": ["button.primary", "button.secondary"],
        "inputs": {"selectors": ["input[name='q']"]},
    })
    assert "button.primary" in scan_script
    assert "input[name='q']" in scan_script


def test_safe_extract_dict() -> None:
    """Проверяет утилиту безопасной десериализации словарей."""
    assert _safe_extract_dict({"a": 1}) == {"a": 1}
    assert _safe_extract_dict('{"key": "value"}') == {"key": "value"}
    assert _safe_extract_dict("invalid json") == {}
    assert _safe_extract_dict([["k1", "v1"], ["k2", {"value": "v2"}]]) == {"k1": "v1", "k2": "v2"}
    assert _safe_extract_dict([{"name": "n1", "value": "val1"}]) == {"n1": "val1"}
    assert _safe_extract_dict(123) == {}


@pytest.mark.asyncio
async def test_recorder_inject_and_poll() -> None:
    """Проверяет внедрение скрипта и опрос состояния через мок-вкладку."""
    mock_poll_data = {
        "finished": False,
        "actions_count": 1,
        "actions": [
            {
                "action_id": 1,
                "event_type": "click",
                "timestamp": "2026-09-25T12:00:00Z",
                "elapsed_seconds": 0.5,
                "tag_name": "button",
                "computed_selector": "button#submit",
                "matched_checklist_id": "submit_step",
            }
        ],
        "checklist": [
            {
                "id": "submit_step",
                "label": "Отправка",
                "completed": True,
                "is_manual": False,
                "action_index": 1,
                "target_selector": "button#submit",
            }
        ],
        "page_url": "https://example.com",
        "page_title": "Example Domain",
        "session_viewport": {
            "width": 1280,
            "height": 800,
            "device_pixel_ratio": 1.0,
            "breakpoint": "compact",
        },
    }

    tab = FakeTab(eval_return_value='{"key": "test"}')
    recorder = DOMActionRecorder(widget_title="Custom HUD")

    injected = await recorder.inject(tab)
    assert injected
    assert len(tab.executed_scripts) == 1
    assert "Custom HUD" in tab.executed_scripts[0]

    tab.eval_return_value = mock_poll_data
    poll_result = await recorder.poll(tab)
    assert poll_result["actions_count"] == 1
    assert poll_result["page_url"] == "https://example.com"

    is_fin = await recorder.is_finished(tab)
    assert not is_fin


def test_build_and_export_report(tmp_path: Path) -> None:
    """Проверяет синтез отчета, генерацию Markdown и сохранение в файлы."""
    raw_data = {
        "page_url": "https://service.local/dashboard",
        "page_title": "Панель управления",
        "session_viewport": {
            "width": 1600,
            "height": 900,
            "device_pixel_ratio": 1.0,
            "breakpoint": "desktop_wide",
        },
        "actions": [
            {
                "action_id": 1,
                "event_type": "click",
                "timestamp": "2026-09-25T12:00:00Z",
                "elapsed_seconds": 0.45,
                "tag_name": "button",
                "aria_label": "Фильтр",
                "role": "button",
                "computed_selector": "button.filter-btn",
                "matched_checklist_id": "open_filter",
                "has_duplicates": True,
                "duplicate_count": 2,
                "container_scope": ".header-panel",
                "scoped_selector": ".header-panel button.filter-btn",
                "mutation_diff": {
                    "spawned_containers": [".dropdown-menu"],
                    "appeared_elements": ["button.item"],
                    "attribute_changes": ["~ attr aria-expanded на <button>"],
                },
            }
        ],
        "checklist": [
            {
                "id": "open_filter",
                "label": "Открыть фильтры",
                "description": "Клик по кнопке фильтров",
                "hints": ["button.filter-btn"],
                "completed": True,
                "is_manual": False,
                "action_index": 1,
                "target_selector": "button.filter-btn",
            }
        ],
    }

    recorder = DOMActionRecorder()
    report = recorder.build_report(raw_data, session_name="test_session", target_name="test_service")

    assert isinstance(report, DOMActionSessionReport)
    assert report.total_actions == 1
    assert report.session_name == "test_session"
    assert report.target_name == "test_service"
    assert "open_filter" in report.discovered_selectors
    assert report.discovered_selectors["open_filter"] == ["button.filter-btn"]

    # Проверка Markdown содержимого
    md = report.summary_markdown
    assert "# 🎥 Отчет записи интерактивных действий DOM (TEST_SERVICE)" in md
    assert "Открыть фильтры" in md
    assert "Предупреждения: Обнаружены селекторы с дубликатами в DOM" in md
    assert "button.filter-btn" in md
    assert ".header-panel button.filter-btn" in md
    assert "1600x900" in md

    # Экспорт в файлы
    json_path = tmp_path / "recording_report.json"
    exported_json, exported_md = recorder.export_report(report, json_path)

    assert exported_json.is_file()
    assert exported_md is not None and exported_md.is_file()
    assert "Панель управления" in exported_json.read_text(encoding="utf-8")
    assert "TEST_SERVICE" in exported_md.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_wait_for_finish_and_callback() -> None:
    """Проверяет цикл wait_for_finish с перехватом действий и завершением по флагу."""
    recorder = DOMActionRecorder()
    captured_actions: list[RecordedAction] = []

    def on_action(act: RecordedAction) -> None:
        captured_actions.append(act)

    iteration = 0

    def mock_eval(script: str) -> Any:
        nonlocal iteration
        iteration += 1
        if iteration == 1:
            return {
                "finished": False,
                "actions": [
                    {
                        "action_id": 1,
                        "event_type": "click",
                        "timestamp": "2026-09-25T12:00:00Z",
                        "elapsed_seconds": 0.1,
                        "tag_name": "a",
                        "computed_selector": "a#link",
                    }
                ],
            }
        return {
            "finished": True,
            "actions": [
                {
                    "action_id": 1,
                    "event_type": "click",
                    "timestamp": "2026-09-25T12:00:00Z",
                    "elapsed_seconds": 0.1,
                    "tag_name": "a",
                    "computed_selector": "a#link",
                }
            ],
            "page_url": "https://example.com/finish",
        }

    tab = FakeTab(eval_return_value=mock_eval)
    report = await recorder.wait_for_finish(tab, poll_interval=0.01, timeout=2.0, on_action=on_action)

    assert len(captured_actions) == 1
    assert captured_actions[0].computed_selector == "a#link"
    assert report.total_actions == 1
    assert report.page_url == "https://example.com/finish"


@pytest.mark.asyncio
async def test_wait_for_finish_timeout() -> None:
    """Проверяет выброс TimeoutError при истечении таймаута записи."""
    recorder = DOMActionRecorder()
    tab = FakeTab(eval_return_value={"finished": False, "actions": []})

    with pytest.raises(asyncio.TimeoutError):
        await recorder.wait_for_finish(tab, poll_interval=0.01, timeout=0.05)


def test_recorder_hud_alias() -> None:
    """Проверяет, что DOMActionRecorderHUD является алиасом DOMActionRecorder."""
    assert DOMActionRecorderHUD is DOMActionRecorder
