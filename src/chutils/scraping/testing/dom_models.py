"""Модели данных для интерактивной записи действий пользователя и инспекции DOM."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ViewportInfo(BaseModel):
    """Параметры области просмотра браузера и адаптивный брейкпоинт.

    Attributes:
        width: Ширина окна в пикселях.
        height: Высота окна в пикселях.
        device_pixel_ratio: Соотношение физических пикселей к CSS (DPR).
        breakpoint: Адаптивный брейкпоинт ("desktop_wide", "compact", "mobile").
    """

    width: int
    height: int
    device_pixel_ratio: float = 1.0
    breakpoint: Literal["desktop_wide", "compact", "mobile"] | str = "compact"


class DOMMutationDiff(BaseModel):
    """Структурированная дельта мутаций DOM после действия пользователя.

    Attributes:
        spawned_containers: Селекторы появившихся контейнеров (оверлеи, диалоги, панели).
        appeared_elements: Селекторы новых интерактивных элементов внутри контейнера.
        attribute_changes: Измененные классы и aria-* атрибуты.
    """

    spawned_containers: list[str] = Field(
        default_factory=list,
        description="Селекторы появившихся контейнеров (оверлеи, диалоги, выпадающие списки)",
    )
    appeared_elements: list[str] = Field(
        default_factory=list,
        description="Селекторы новых интерактивных элементов внутри контейнера",
    )
    attribute_changes: list[str] = Field(
        default_factory=list,
        description="Измененные классы и aria-* атрибуты (aria-expanded, disabled и др.)",
    )


class RecordedChecklistItem(BaseModel):
    """Элемент интерактивного чеклиста действий пользователя.

    Attributes:
        id: Уникальный строковый идентификатор пункта.
        label: Отображаемое название пункта в HUD.
        description: Подробное описание выполняемого действия.
        hints: Список селекторов и визуальных ориентиров элемента.
        completed: Флаг завершения шага.
        is_manual: Флаг подтверждения пользователем вручную.
        action_index: Номер связанного действия пользователя.
        target_selector: Зафиксированный итоговый селектор элемента.
    """

    id: str
    label: str
    description: str = ""
    hints: list[str] = Field(
        default_factory=list,
        description="Селекторы и визуальные ориентиры целевого элемента",
    )
    completed: bool = False
    is_manual: bool = Field(
        default=False,
        description="Флаг подтверждения пользователем вручную",
    )
    action_index: int | None = None
    target_selector: str | None = None


class RecordedAction(BaseModel):
    """Зафиксированное действие пользователя с элементом интерфейса.

    Attributes:
        action_id: Порядковый номер действия в сессии.
        event_type: Тип события браузера ("click", "input", "change", "keydown").
        timestamp: Временная метка ISO 8601.
        elapsed_seconds: Секунды с момента старта записи.
        tag_name: Имя HTML-тега элемента.
        element_id: Значение id элемента (если есть).
        class_names: CSS-классы элемента.
        aria_label: Значение aria-label атрибута.
        role: ARIA-роль элемента.
        text_snippet: Текстовое содержимое элемента (фрагмент).
        value_snippet: Введенное строковое значение.
        computed_selector: Основной сгенерированный селектор элемента.
        alternative_selectors: Список альтернативных селекторов.
        xpath: XPath-путь к элементу (опционально).
        outer_html: HTML-сниппет элемента.
        parent_summary: Описание непосредственного родителя.
        matched_checklist_id: Идентификатор пункта чеклиста, с которым сопоставлено действие.
        mutations: Список произошедших мутаций DOM.
        viewport: Информация о вьюпорте на момент взаимодействия.
        container_scope: Контекст родительского оверлея или модального окна.
        scoped_selector: Составной селектор с учетом контейнера.
        duplicate_count: Количество найденных совпадений в DOM.
        has_duplicates: Флаг наличия дубликатов селектора.
        mutation_diff: Детализированный отчет мутаций.
    """

    action_id: int
    event_type: str
    timestamp: str
    elapsed_seconds: float
    tag_name: str
    element_id: str | None = None
    class_names: str | None = None
    aria_label: str | None = None
    role: str | None = None
    text_snippet: str | None = None
    value_snippet: str | None = None
    computed_selector: str
    alternative_selectors: list[str] = Field(default_factory=list)
    xpath: str | None = None
    outer_html: str | None = None
    parent_summary: str | None = None
    matched_checklist_id: str | None = None
    mutations: list[str] = Field(default_factory=list)
    viewport: ViewportInfo | None = None
    container_scope: str | None = None
    scoped_selector: str | None = None
    duplicate_count: int = 1
    has_duplicates: bool = False
    mutation_diff: DOMMutationDiff | None = None


class DOMActionSessionReport(BaseModel):
    """Итоговый структурированный отчет интерактивной сессии записи действий.

    Attributes:
        timestamp: Временная метка сессии ISO 8601.
        session_name: Имя профиля или сессии.
        target_name: Имя целевого сайта или провайдера.
        page_url: URL целевой страницы.
        page_title: Заголовок веб-страницы.
        total_actions: Общее число зафиксированных действий.
        session_viewport: Разрешение вьюпорта браузера.
        actions: Список зафиксированных действий.
        checklist: Список пунктов чеклиста с результатами.
        discovered_selectors: Словарь обнаруженных селекторов по категориям.
        summary_markdown: Итоговый сгенерированный Markdown-отчет.
    """

    timestamp: str
    session_name: str = "default"
    target_name: str = "web"
    page_url: str = ""
    page_title: str = ""
    total_actions: int = 0
    session_viewport: ViewportInfo | None = None
    actions: list[RecordedAction] = Field(default_factory=list)
    checklist: list[RecordedChecklistItem] = Field(default_factory=list)
    discovered_selectors: dict[str, list[str]] = Field(default_factory=dict)
    summary_markdown: str = ""
