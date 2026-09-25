"""JavaScript-скрипты браузерной инспекции разметки, полифилов селекторов и HUD-виджета."""  # chutils: ignore[CodeDecompositionRule]

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from .dom_models import RecordedChecklistItem

CORE_DOM_HELPERS_JS: str = r"""
function isElementVisible(el) {
    if (!el || !(el instanceof Element)) return false;
    try {
        if (el.offsetParent === null && el.offsetWidth === 0 && el.offsetHeight === 0) {
            return false;
        }
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity || '1') < 0.05) {
            return false;
        }
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) {
            return false;
        }
        return true;
    } catch (e) {
        return false;
    }
}

function queryAllSafe(sel) {
    try {
        return Array.from(document.querySelectorAll(sel));
    } catch (err) {
        const containsMatch = sel.match(/^(.*?):contains\(['"](.*?)['"]\)(.*)$/);
        if (containsMatch) {
            const [, base, text] = containsMatch;
            const candidates = Array.from(document.querySelectorAll(base || '*'));
            return candidates.filter(el => (el.textContent || '').includes(text));
        }
        const hasTextMatch = sel.match(/^(.*?):has-text\(['"](.*?)['"]\)(.*)$/);
        if (hasTextMatch) {
            const [, base, text] = hasTextMatch;
            const candidates = Array.from(document.querySelectorAll(base || '*'));
            return candidates.filter(el => (el.textContent || '').includes(text));
        }
        throw err;
    }
}

function getViewportInfo() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    let bp = 'compact';
    if (w > 1440) bp = 'desktop_wide';
    else if (w <= 1024) bp = 'mobile';
    return {
        width: w,
        height: h,
        device_pixel_ratio: window.devicePixelRatio || 1,
        breakpoint: bp
    };
}

function getCssSelector(el) {
    if (!(el instanceof Element)) return '';
    if (el.id && !el.id.match(/^[:\d]|\s/)) {
        const idSel = '#' + CSS.escape(el.id);
        if (document.querySelectorAll(idSel).length === 1) return idSel;
    }

    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel && ariaLabel.trim()) {
        const sel = `${el.tagName.toLowerCase()}[aria-label="${CSS.escape(ariaLabel.trim())}"]`;
        if (document.querySelectorAll(sel).length === 1) return sel;
    }

    for (const attr of ['data-testid', 'data-test-id', 'data-test', 'data-cy', 'role', 'name', 'placeholder']) {
        const val = el.getAttribute(attr);
        if (val) {
            const sel = `${el.tagName.toLowerCase()}[${attr}="${CSS.escape(val)}"]`;
            if (document.querySelectorAll(sel).length === 1) return sel;
        }
    }

    const tag = el.tagName.toLowerCase();
    if (tag.includes('-')) {
        if (document.querySelectorAll(tag).length === 1) return tag;
    }

    const path = [];
    let cur = el;
    while (cur && cur.nodeType === Node.ELEMENT_NODE && cur !== document.body) {
        let selector = cur.tagName.toLowerCase();
        if (cur.className && typeof cur.className === 'string') {
            const classes = cur.className.trim().split(/\s+/)
                .filter(c => c && !c.startsWith('ng-') && !c.includes(':') && !c.match(/^\d/));
            if (classes.length > 0) {
                selector += '.' + classes.slice(0, 2).map(c => CSS.escape(c)).join('.');
            }
        }
        path.unshift(selector);
        try {
            const fullSel = path.join(' > ');
            if (document.querySelectorAll(fullSel).length === 1) return fullSel;
        } catch (e) {}
        if (path.length >= 3) break;
        cur = cur.parentElement;
    }

    return path.join(' > ') || el.tagName.toLowerCase();
}

function getAlternativeSelectors(el) {
    if (!(el instanceof Element)) return [];
    const alts = [];
    const tag = el.tagName.toLowerCase();
    const aria = el.getAttribute('aria-label');
    if (aria) alts.push(`${tag}[aria-label*="${CSS.escape(aria)}" i]`);
    const role = el.getAttribute('role');
    if (role) alts.push(`${tag}[role="${CSS.escape(role)}"]`);
    if (el.className && typeof el.className === 'string') {
        const cls = el.className.trim().split(/\s+/).find(c => !c.startsWith('ng-'));
        if (cls) alts.push(`${tag}.${CSS.escape(cls)}`);
    }
    if (el.parentElement) {
        const ptag = el.parentElement.tagName.toLowerCase();
        alts.push(`${ptag} ${tag}`);
    }
    return [...new Set(alts)].slice(0, 4);
}

function checkDuplicates(selector) {
    try {
        const matches = document.querySelectorAll(selector);
        return {
            count: matches.length,
            has_duplicates: matches.length > 1
        };
    } catch (e) {
        return { count: 1, has_duplicates: false };
    }
}

function getContainerScope(el, customScopes) {
    if (!(el instanceof Element)) return null;
    const defaultScopes = [
        'dialog',
        '[role="dialog"]',
        '[role="alertdialog"]',
        '[role="menu"]',
        '.modal',
        '.cdk-overlay-pane',
        'mat-dialog-container',
        '.mat-mdc-menu-panel',
        '.mat-mdc-select-panel'
    ];
    const scopes = (customScopes && customScopes.length > 0) ? customScopes : defaultScopes;
    for (const scopeSel of scopes) {
        try {
            const container = el.closest(scopeSel);
            if (container) {
                return scopeSel;
            }
        } catch (e) {}
    }
    return null;
}
"""
"""Универсальные вспомогательные функции JavaScript для работы с DOM."""


PAGE_META_SCRIPT: str = r"""
JSON.stringify((() => {
    return {
        url: window.location.href,
        title: document.title,
        ready_state: document.readyState
    };
})())
"""
"""JS-скрипт получения базовых метаданных страницы (URL, title, readyState)."""


def build_scan_selectors_script(groups: dict[str, list[str] | dict[str, Any]]) -> str:
    """Генерирует JS-скрипт для полного сканирования и диагностики групп селекторов.

    Args:
        groups: Конфигурация групп селекторов. Значением может быть список строк-селекторов
            или словарь со свойством "selectors".

    Returns:
        Исходный код JavaScript, возвращающий диагностику через JSON.stringify.
    """
    normalized_groups: dict[str, dict[str, list[str]]] = {}
    for name, def_val in groups.items():
        if isinstance(def_val, dict) and "selectors" in def_val:
            raw_selectors = def_val["selectors"]
            selectors_list = raw_selectors if isinstance(raw_selectors, list) else [raw_selectors]
        elif isinstance(def_val, list):
            selectors_list = def_val
        else:
            selectors_list = [str(def_val)]
        normalized_groups[name] = {"selectors": selectors_list}

    js_groups_json = json.dumps(normalized_groups, ensure_ascii=False)

    return f"""
    JSON.stringify((() => {{
        {CORE_DOM_HELPERS_JS}

        const groups = {js_groups_json};
        const results = {{}};

        for (const [groupName, groupDef] of Object.entries(groups)) {{
            const details = [];
            for (const sel of groupDef.selectors) {{
                try {{
                    const elements = queryAllSafe(sel);
                    if (elements.length === 0) {{
                        details.push({{
                            selector: sel,
                            found: false,
                            count: 0,
                            visible: false,
                            visible_count: 0,
                            duplicate_conflict: false,
                            enabled: true,
                            tag_name: null,
                            class_names: null,
                            text_snippet: null,
                            attributes: {{}},
                            error: null,
                        }});
                        continue;
                    }}

                    let anyVisible = false;
                    let visibleCount = 0;
                    let firstVisibleEl = null;
                    for (const el of elements) {{
                        if (isElementVisible(el)) {{
                            anyVisible = true;
                            visibleCount++;
                            if (!firstVisibleEl) firstVisibleEl = el;
                        }}
                    }}

                    const duplicateConflict = (elements.length > 1 && visibleCount > 0 && visibleCount < elements.length);
                    const targetEl = firstVisibleEl || elements[0];
                    const tag = targetEl.tagName ? targetEl.tagName.toLowerCase() : null;
                    const classes = targetEl.className && typeof targetEl.className === 'string'
                        ? targetEl.className.trim()
                        : null;
                    const rawText = (targetEl.innerText || targetEl.textContent || '').trim().replace(/\\s+/g, ' ');
                    const snippet = rawText ? rawText.slice(0, 80) : null;

                    const attrs = {{}};
                    const checkAttrs = ['aria-label', 'role', 'data-testid', 'data-test-id', 'type', 'id', 'name', 'placeholder'];
                    for (const attr of checkAttrs) {{
                        if (targetEl.hasAttribute && targetEl.hasAttribute(attr)) {{
                            attrs[attr] = targetEl.getAttribute(attr);
                        }}
                    }}
                    const isEnabled = !targetEl.disabled && targetEl.getAttribute('aria-disabled') !== 'true';

                    details.push({{
                        selector: sel,
                        found: true,
                        count: elements.length,
                        visible: anyVisible,
                        visible_count: visibleCount,
                        duplicate_conflict: duplicateConflict,
                        enabled: isEnabled,
                        tag_name: tag,
                        class_names: classes,
                        text_snippet: snippet,
                        attributes: attrs,
                        error: null,
                    }});
                }} catch (err) {{
                    details.push({{
                        selector: sel,
                        found: false,
                        count: 0,
                        visible: false,
                        visible_count: 0,
                        duplicate_conflict: false,
                        enabled: false,
                        tag_name: null,
                        class_names: null,
                        text_snippet: null,
                        attributes: {{}},
                        error: String(err.message || err),
                    }});
                }}
            }}
            results[groupName] = details;
        }}
        return results;
    }})())
    """


def get_recorder_hud_ui_js() -> str:
    """Возвращает JavaScript код рендеринга и управления плавающим HUD виджетом.

    Построен с соблюдением требований Trusted Types (без использования innerHTML).

    Returns:
        Строка JavaScript кода функций renderChecklist, updateHudDisplay и createHud.
    """
    return """
    function renderChecklist() {
        try {
            const cont = document.getElementById('chutils-checklist-container');
            if (!cont || !window.__chutilsChecklist) return;
            while (cont.firstChild) {
                cont.removeChild(cont.firstChild);
            }

            for (const item of window.__chutilsChecklist) {
                const row = document.createElement('div');
                row.className = 'chutils-checklist-row';
                row.style.cssText = `
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 6px;
                    padding: 4px 6px;
                    border-radius: 6px;
                    color: ${item.completed ? '#a6e3a1' : '#bac2de'};
                    font-size: 11px;
                    cursor: pointer;
                    transition: background 0.15s, color 0.15s;
                    user-select: none;
                `;
                row.onmouseenter = () => {
                    row.style.background = 'rgba(255, 255, 255, 0.07)';
                };
                row.onmouseleave = () => {
                    row.style.background = 'transparent';
                };

                const hintText = (item.hints && item.hints.length > 0) ? `\\nОриентиры: ${item.hints.join(', ')}` : '';
                row.title = `${item.label}\\n${item.description || ''}${hintText}\\n\\n[Кликните для ручной отметки или привязки к последнему действию]`;

                const left = document.createElement('div');
                left.style.cssText = 'display: flex; align-items: center; gap: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;';

                const icon = document.createElement('span');
                icon.textContent = item.completed ? (item.is_manual ? '👌' : '✅') : '⬜';
                icon.style.cssText = 'flex-shrink: 0; font-size: 11px;';

                const label = document.createElement('span');
                label.textContent = item.label;
                if (item.completed) {
                    label.style.textDecoration = 'line-through';
                    label.style.opacity = '0.85';
                }
                left.appendChild(icon);
                left.appendChild(label);
                row.appendChild(left);

                if (item.completed && item.target_selector) {
                    const badge = document.createElement('span');
                    badge.style.cssText = 'font-size: 9px; padding: 1px 4px; background: rgba(166, 227, 161, 0.2); border-radius: 3px; color: #a6e3a1; flex-shrink: 0;';
                    badge.textContent = item.is_manual ? 'руч.' : 'auto';
                    row.appendChild(badge);
                }

                row.onclick = (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (!item.completed) {
                        const lastAct = (window.__chutilsRecordedActions && window.__chutilsRecordedActions.length > 0)
                            ? window.__chutilsRecordedActions[window.__chutilsRecordedActions.length - 1]
                            : null;
                        item.completed = true;
                        item.is_manual = true;
                        if (lastAct) {
                            item.action_index = lastAct.action_id;
                            item.target_selector = lastAct.computed_selector;
                            lastAct.matched_checklist_id = item.id;
                        } else {
                            item.target_selector = 'manual_confirm';
                        }
                    } else {
                        item.completed = false;
                        item.is_manual = false;
                        item.action_index = null;
                        item.target_selector = null;
                    }
                    renderChecklist();
                };

                cont.appendChild(row);
            }

            const tip = document.createElement('div');
            tip.style.cssText = 'font-size: 10px; color: #6c7086; margin-top: 6px; padding-top: 4px; border-top: 1px dashed rgba(255,255,255,0.06); line-height: 1.3;';
            tip.textContent = '💡 Кликните по шагу для привязки к последнему действию или ручной отметки.';
            cont.appendChild(tip);
        } catch (err) {
            console.error('[chutils.recorder] renderChecklist error:', err);
        }
    }

    function updateHudDisplay(action) {
        try {
            const vp = getViewportInfo();
            const vpEl = document.getElementById('chutils-viewport-badge');
            if (vpEl) {
                vpEl.textContent = `${vp.width}x${vp.height} [${vp.breakpoint}]`;
            }

            const cnt = document.getElementById('chutils-action-count');
            if (cnt) {
                const total = window.__chutilsRecordedActions.length;
                cnt.textContent = `${total} действий`;
            }

            const last = document.getElementById('chutils-last-action');
            if (last && action) {
                const sel = action.scoped_selector || action.computed_selector;
                const mutCount = (action.mutations || []).length;
                const diffSpawns = (action.mutation_diff && action.mutation_diff.spawned_containers) ? action.mutation_diff.spawned_containers.length : 0;
                let metaExtra = `+${mutCount} mut`;
                if (diffSpawns > 0) metaExtra += `, +${diffSpawns} panels`;
                if (action.has_duplicates) metaExtra += `, ⚠️ dup x${action.duplicate_count}`;
                last.textContent = `[${action.event_type}] ${sel} (${metaExtra})`;
            }

            renderChecklist();
        } catch (err) {
            console.error('[chutils.recorder] updateHudDisplay error:', err);
        }
    }

    function createHud() {
        try {
            const existing = document.getElementById('chutils-action-recorder-hud');
            if (existing) existing.remove();

            const hud = document.createElement('div');
            hud.id = 'chutils-action-recorder-hud';
            hud.style.cssText = `
                position: fixed !important;
                bottom: 24px !important;
                right: 24px !important;
                width: 380px !important;
                max-height: 85vh !important;
                background: #1e1e2e !important;
                border: 2px solid #89b4fa !important;
                border-radius: 12px !important;
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.75) !important;
                color: #cdd6f4 !important;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
                font-size: 12px !important;
                z-index: 2147483647 !important;
                display: flex !important;
                flex-direction: column !important;
                overflow: hidden !important;
                user-select: none !important;
                opacity: 1 !important;
                visibility: visible !important;
                pointer-events: auto !important;
            `;

            const header = document.createElement('div');
            header.id = 'chutils-hud-header';
            header.style.cssText = 'padding: 10px 14px; background: rgba(30, 30, 46, 0.95); border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; justify-content: space-between; align-items: center; cursor: move;';

            const title = document.createElement('div');
            title.style.cssText = 'font-weight: bold; color: #89b4fa; display: flex; align-items: center; gap: 6px; pointer-events: none;';
            const icon = document.createElement('span');
            icon.textContent = '🎥';
            const titleText = document.createElement('span');
            titleText.textContent = window.__chutilsProviderTitle || 'Запись действий DOM';
            const dot = document.createElement('span');
            dot.style.cssText = 'display: inline-block; width: 8px; height: 8px; background: #a6e3a1; border-radius: 50%; box-shadow: 0 0 6px #a6e3a1;';
            title.appendChild(icon);
            title.appendChild(titleText);
            title.appendChild(dot);

            const headerRight = document.createElement('div');
            headerRight.style.cssText = 'display: flex; align-items: center; gap: 6px;';

            const vp = getViewportInfo();
            const vpEl = document.createElement('div');
            vpEl.id = 'chutils-viewport-badge';
            vpEl.style.cssText = 'font-size: 9px; padding: 2px 4px; background: rgba(137, 180, 250, 0.15); border: 1px solid rgba(137, 180, 250, 0.3); border-radius: 4px; color: #89b4fa;';
            vpEl.textContent = `${vp.width}x${vp.height} [${vp.breakpoint}]`;

            const count = document.createElement('div');
            count.id = 'chutils-action-count';
            count.style.cssText = 'font-size: 11px; color: #a6adc8; background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 10px; font-variant-numeric: tabular-nums;';
            count.textContent = '0 действий';

            const minBtn = document.createElement('button');
            minBtn.id = 'chutils-hud-min-btn';
            minBtn.style.cssText = 'background: transparent; border: none; color: #a6adc8; cursor: pointer; font-size: 13px; padding: 0 4px; line-height: 1;';
            minBtn.textContent = '➖';
            minBtn.title = 'Свернуть / развернуть виджет';

            headerRight.appendChild(vpEl);
            headerRight.appendChild(count);
            headerRight.appendChild(minBtn);

            header.appendChild(title);
            header.appendChild(headerRight);
            hud.appendChild(header);

            const bodyWrapper = document.createElement('div');
            bodyWrapper.id = 'chutils-hud-body';
            bodyWrapper.style.cssText = 'display: flex; flex-direction: column; overflow: hidden;';

            const checklistSection = document.createElement('div');
            checklistSection.style.cssText = 'padding: 8px 12px; background: rgba(17, 17, 27, 0.6); border-bottom: 1px solid rgba(255,255,255,0.05); max-height: 220px; overflow-y: auto;';

            const chkHeader = document.createElement('div');
            chkHeader.style.cssText = 'font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: #6c7086; margin-bottom: 4px; font-weight: bold;';
            chkHeader.textContent = 'Чеклист целевых действий:';
            checklistSection.appendChild(chkHeader);

            const chkContainer = document.createElement('div');
            chkContainer.id = 'chutils-checklist-container';
            chkContainer.style.cssText = 'display: flex; flex-direction: column; gap: 2px;';
            checklistSection.appendChild(chkContainer);
            bodyWrapper.appendChild(checklistSection);

            const lastDiv = document.createElement('div');
            lastDiv.style.cssText = 'padding: 6px 12px; font-size: 11px; background: rgba(17, 17, 27, 0.4); border-bottom: 1px solid rgba(255,255,255,0.05);';
            const lastLabel = document.createElement('span');
            lastLabel.textContent = 'Последний: ';
            const lastCode = document.createElement('code');
            lastCode.id = 'chutils-last-action';
            lastCode.style.cssText = 'color: #f9e2af; word-break: break-all;';
            lastCode.textContent = 'Ожидание взаимодействия...';
            lastDiv.appendChild(lastLabel);
            lastDiv.appendChild(lastCode);
            bodyWrapper.appendChild(lastDiv);

            const footer = document.createElement('div');
            footer.style.cssText = 'padding: 10px 14px; display: flex; gap: 8px; background: rgba(24, 24, 37, 0.95);';
            const finishBtn = document.createElement('button');
            finishBtn.id = 'chutils-finish-btn';
            finishBtn.style.cssText = 'flex: 1; padding: 8px 12px; background: #a6e3a1; color: #11111b; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; transition: background 0.15s;';
            finishBtn.textContent = '💾 Завершить запись';
            finishBtn.onclick = (e) => {
                e.stopPropagation();
                e.preventDefault();
                window.__chutilsRecordFinished = true;
                finishBtn.textContent = '✅ Завершено';
                finishBtn.style.background = '#89b4fa';
            };
            footer.appendChild(finishBtn);
            bodyWrapper.appendChild(footer);

            hud.appendChild(bodyWrapper);

            let isMinimized = false;
            minBtn.onclick = (e) => {
                e.stopPropagation();
                e.preventDefault();
                isMinimized = !isMinimized;
                if (isMinimized) {
                    bodyWrapper.style.display = 'none';
                    minBtn.textContent = '➕';
                    hud.style.width = '260px';
                } else {
                    bodyWrapper.style.display = 'flex';
                    minBtn.textContent = '➖';
                    hud.style.width = '380px';
                }
            };

            let isDragging = false;
            let dragStartX = 0;
            let dragStartY = 0;
            let hudStartLeft = 0;
            let hudStartTop = 0;

            header.onmousedown = (e) => {
                if (e.target === minBtn) return;
                isDragging = true;
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                const rect = hud.getBoundingClientRect();
                hudStartLeft = rect.left;
                hudStartTop = rect.top;
                hud.style.bottom = 'auto';
                hud.style.right = 'auto';
                hud.style.left = `${hudStartLeft}px`;
                hud.style.top = `${hudStartTop}px`;
                e.preventDefault();
            };

            window.addEventListener('mousemove', (e) => {
                if (!isDragging) return;
                const dx = e.clientX - dragStartX;
                const dy = e.clientY - dragStartY;
                const nextLeft = Math.max(10, Math.min(window.innerWidth - hud.offsetWidth - 10, hudStartLeft + dx));
                const nextTop = Math.max(10, Math.min(window.innerHeight - hud.offsetHeight - 10, hudStartTop + dy));
                hud.style.left = `${nextLeft}px`;
                hud.style.top = `${nextTop}px`;
            }, true);

            window.addEventListener('mouseup', () => {
                isDragging = false;
            }, true);

            const root = document.body || document.documentElement;
            if (root) {
                root.appendChild(hud);
            }

            renderChecklist();

            if (!window.__chutilsHudWatcher) {
                window.__chutilsHudWatcher = setInterval(() => {
                    if (!document.getElementById('chutils-action-recorder-hud')) {
                        createHud();
                    }
                }, 800);
            }
        } catch (err) {
            console.error('[chutils.recorder] Ошибка создания HUD:', err);
        }
    }
    """


POLL_RECORDED_ACTIONS_SCRIPT: str = """
JSON.stringify((() => {
    let vp = null;
    try {
        const w = window.innerWidth;
        const h = window.innerHeight;
        let bp = 'compact';
        if (w > 1440) bp = 'desktop_wide';
        else if (w <= 1024) bp = 'mobile';
        vp = {
            width: w,
            height: h,
            device_pixel_ratio: window.devicePixelRatio || 1,
            breakpoint: bp
        };
    } catch (e) {}

    return {
        finished: Boolean(window.__chutilsRecordFinished),
        actions_count: (window.__chutilsRecordedActions || []).length,
        actions: window.__chutilsRecordedActions || [],
        checklist: window.__chutilsChecklist || [],
        page_url: window.location.href,
        page_title: document.title,
        session_viewport: vp
    };
})())
"""
"""JS-скрипт опроса текущего состояния записи действий."""


def build_inject_recorder_hud_script(
    checklist: Sequence[dict[str, Any] | RecordedChecklistItem] | None = None,
    widget_title: str = "Запись действий DOM",
    container_selectors: list[str] | None = None,
    custom_matcher_js: str | None = None,
) -> str:
    """Генерирует JS-скрипт внедрения перехватчика действий и плавающего виджета-шпаргалки.

    Args:
        checklist: Список пунктов чеклиста с id, label, description, hints.
        widget_title: Отображаемый заголовок в шапке HUD.
        container_selectors: Дополнительные селекторы модальных окон/панелей.
        custom_matcher_js: Пользовательский код функции сопоставления элемента с чеклистом:
            `(el, evType) => string | null`.

    Returns:
        Строка JavaScript для вызова в браузере через evaluate.
    """
    prepared_items: list[dict[str, Any]] = []
    if checklist:
        for item in checklist:
            if isinstance(item, RecordedChecklistItem):
                prepared_items.append(item.model_dump())
            elif isinstance(item, dict):
                prepared_items.append(dict(item))

    items_json = json.dumps(prepared_items, ensure_ascii=False)
    title_escaped = json.dumps(widget_title, ensure_ascii=False)
    scopes_json = json.dumps(container_selectors or [], ensure_ascii=False)

    matcher_code = (
        custom_matcher_js
        if custom_matcher_js
        else r"""
    function matchChecklistItem(el, evType) {
        if (!window.__chutilsChecklist || window.__chutilsChecklist.length === 0) return null;
        const text = (el.innerText || el.textContent || '').toLowerCase();
        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
        const tag = el.tagName.toLowerCase();
        const role = (el.getAttribute('role') || '').toLowerCase();
        const cls = (typeof el.className === 'string' ? el.className : '').toLowerCase();

        for (const item of window.__chutilsChecklist) {
            if (!item.hints || item.hints.length === 0) continue;
            for (const hint of item.hints) {
                const h = hint.toLowerCase();
                try {
                    if (el.matches && el.matches(hint)) return item.id;
                } catch (e) {}
                if (aria.includes(h) || text.includes(h) || cls.includes(h) || tag === h || role === h) {
                    return item.id;
                }
            }
        }
        return null;
    }
    """
    )

    return f"""
(() => {{
    if (window.__chutilsRecorderInstalled) {{
        if (!document.getElementById('chutils-action-recorder-hud')) {{
            if (typeof window.__chutilsCreateHud === 'function') {{
                window.__chutilsCreateHud();
            }}
        }}
        return true;
    }}

    {CORE_DOM_HELPERS_JS}

    window.__chutilsRecordStartTime = performance.now();
    window.__chutilsRecordedActions = [];
    window.__chutilsRecordFinished = false;
    window.__chutilsProviderTitle = {title_escaped};
    window.__chutilsChecklist = {items_json}.map(item => ({{
        ...item,
        completed: Boolean(item.completed),
        is_manual: Boolean(item.is_manual),
        action_index: item.action_index || null,
        target_selector: item.target_selector || null
    }}));
    const customContainerScopes = {scopes_json};

    {matcher_code}

    let recentMutations = [];
    let pendingContainers = [];
    let pendingAppeared = [];
    let pendingAttrChanges = [];

    try {{
        const observer = new MutationObserver((muts) => {{
            for (const m of muts) {{
                if (m.target && m.target.closest && m.target.closest('#chutils-action-recorder-hud')) continue;
                if (m.type === 'childList') {{
                    for (const node of m.addedNodes) {{
                        if (node instanceof Element) {{
                            const tag = node.tagName.toLowerCase();
                            if (tag.startsWith('script') || tag.startsWith('style')) continue;
                            const cls = (node.className || '').toString();
                            recentMutations.push(`+ <${{tag}} class="${{cls.slice(0, 40)}}">`);

                            const containerMatches = [
                                'dialog',
                                '[role="dialog"]',
                                '[role="alertdialog"]',
                                '[role="menu"]',
                                '.modal',
                                '.cdk-overlay-pane',
                                ...customContainerScopes
                            ];
                            for (const cSel of containerMatches) {{
                                try {{
                                    if (node.matches && node.matches(cSel)) {{
                                        if (!pendingContainers.includes(cSel)) pendingContainers.push(cSel);
                                    }} else if (node.querySelector && node.querySelector(cSel)) {{
                                        if (!pendingContainers.includes(cSel)) pendingContainers.push(cSel);
                                    }}
                                }} catch (e) {{}}
                            }}

                            const interactive = ['button', 'textarea', 'input', 'select', '[role="option"]', '[role="button"]'];
                            for (const iSel of interactive) {{
                                try {{
                                    if (node.matches && node.matches(iSel)) {{
                                        const elSel = getCssSelector(node);
                                        if (elSel && !pendingAppeared.includes(elSel)) pendingAppeared.push(elSel);
                                    }}
                                }} catch (e) {{}}
                            }}
                        }}
                    }}
                }} else if (m.type === 'attributes') {{
                    const tag = m.target.tagName.toLowerCase();
                    const attrMsg = `~ attr ${{m.attributeName}} на <${{tag}}>`;
                    recentMutations.push(attrMsg);
                    if (!pendingAttrChanges.includes(attrMsg)) pendingAttrChanges.push(attrMsg);
                }}
            }}
            if (recentMutations.length > 15) recentMutations = recentMutations.slice(-15);
            if (pendingContainers.length > 5) pendingContainers = pendingContainers.slice(-5);
            if (pendingAppeared.length > 8) pendingAppeared = pendingAppeared.slice(-8);
            if (pendingAttrChanges.length > 8) pendingAttrChanges = pendingAttrChanges.slice(-8);
        }});
        const obsRoot = document.body || document.documentElement;
        if (obsRoot) {{
            observer.observe(obsRoot, {{ childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style', 'disabled', 'aria-expanded'] }});
        }}
    }} catch (obsErr) {{
        console.warn('[chutils.recorder] MutationObserver warning:', obsErr);
    }}

    function recordEvent(e) {{
        const target = e.target;
        if (!target || !(target instanceof Element)) return;
        if (target.closest('#chutils-action-recorder-hud')) return;

        const now = performance.now();
        const elapsed = Math.round((now - window.__chutilsRecordStartTime) / 10) / 100;
        const selector = getCssSelector(target);
        const alts = getAlternativeSelectors(target);
        const matchedItem = matchChecklistItem(target, e.type);

        const currentVp = getViewportInfo();
        const containerScope = getContainerScope(target, customContainerScopes);
        const scopedSelector = (containerScope && selector && !selector.startsWith(containerScope))
            ? `${{containerScope}} ${{selector}}`
            : selector;
        const dupCheck = checkDuplicates(selector);

        const mutationDiff = {{
            spawned_containers: [...pendingContainers],
            appeared_elements: [...pendingAppeared],
            attribute_changes: [...pendingAttrChanges]
        }};
        pendingContainers = [];
        pendingAppeared = [];
        pendingAttrChanges = [];

        const actionObj = {{
            action_id: window.__chutilsRecordedActions.length + 1,
            event_type: e.type,
            timestamp: new Date().toISOString(),
            elapsed_seconds: elapsed,
            tag_name: target.tagName.toLowerCase(),
            element_id: target.id || null,
            class_names: (target.className && typeof target.className === 'string') ? target.className : null,
            aria_label: target.getAttribute('aria-label') || null,
            role: target.getAttribute('role') || null,
            text_snippet: (target.innerText || target.textContent || '').trim().slice(0, 100) || null,
            value_snippet: (target.value !== undefined) ? String(target.value).slice(0, 100) : null,
            computed_selector: selector,
            alternative_selectors: alts,
            xpath: null,
            outer_html: target.outerHTML ? target.outerHTML.slice(0, 500) : null,
            parent_summary: target.parentElement ? `<${{target.parentElement.tagName.toLowerCase()}} class="${{target.parentElement.className || ''}}">` : null,
            matched_checklist_id: matchedItem,
            mutations: [...recentMutations],
            viewport: currentVp,
            container_scope: containerScope,
            scoped_selector: scopedSelector,
            duplicate_count: dupCheck.count,
            has_duplicates: dupCheck.has_duplicates,
            mutation_diff: mutationDiff
        }};
        recentMutations = [];

        if (e.type === 'click') {{
            setTimeout(() => {{
                if (pendingContainers.length > 0) {{
                    for (const pc of pendingContainers) {{
                        if (!actionObj.mutation_diff.spawned_containers.includes(pc)) {{
                            actionObj.mutation_diff.spawned_containers.push(pc);
                        }}
                    }}
                }}
                if (pendingAppeared.length > 0) {{
                    for (const pa of pendingAppeared) {{
                        if (!actionObj.mutation_diff.appeared_elements.includes(pa)) {{
                            actionObj.mutation_diff.appeared_elements.push(pa);
                        }}
                    }}
                }}
            }}, 400);
        }}

        window.__chutilsRecordedActions.push(actionObj);

        if (matchedItem) {{
            const item = window.__chutilsChecklist.find(i => i.id === matchedItem);
            if (item && !item.completed) {{
                item.completed = true;
                item.action_index = actionObj.action_id;
                item.target_selector = selector;
            }}
        }}

        updateHudDisplay(actionObj);
    }}

    window.addEventListener('click', recordEvent, true);
    window.addEventListener('input', recordEvent, true);
    window.addEventListener('change', recordEvent, true);

    {get_recorder_hud_ui_js()}

    window.__chutilsCreateHud = createHud;
    createHud();
    window.__chutilsRecorderInstalled = true;
    return true;
}})()
"""


__all__ = [
    "CORE_DOM_HELPERS_JS",
    "PAGE_META_SCRIPT",
    "POLL_RECORDED_ACTIONS_SCRIPT",
    "build_inject_recorder_hud_script",
    "build_scan_selectors_script",
    "get_recorder_hud_ui_js",
]
