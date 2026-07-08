"""Юнит-тесты для модуля сборки контекста chat_context."""

from pathlib import Path

import pytest

from chutils.dev.chat_context import (
    extract_keywords,
    score_node,
    filter_node_by_modules,
    filter_symbols_by_layer,
    filter_examples,
    collect_context_slice,
)
from chutils.dev.models import Node, Symbol, ProjectExample, ProjectIndex


@pytest.fixture
def sample_index():
    """Фикстура тестового AST-индекса."""
    symbol_public = Symbol(
        name="public_func",
        type="function",
        layer="public",
        signature="def public_func() -> None",
        summary="A public function for testing",
    )
    symbol_internal = Symbol(
        name="internal_func",
        type="function",
        layer="internal",
        signature="def internal_func() -> None",
        summary="An internal helper function",
    )
    symbol_infra = Symbol(
        name="infra_func",
        type="function",
        layer="infrastructure",
        signature="def infra_func() -> None",
        summary="An infrastructure adapter function",
    )

    node_logger = Node(
        name="logger",
        path="src/chutils/logger.py",
        type="module",
        layer="public",
        summary="Logger subsystem",
        symbols=[symbol_public, symbol_internal],
    )

    node_secrets = Node(
        name="secret_manager",
        path="src/chutils/secret_manager.py",
        type="module",
        layer="public",
        summary="Secret Manager subsystem",
        symbols=[symbol_infra],
    )

    root_node = Node(
        name="chutils",
        path="src/chutils",
        type="package",
        layer="public",
        summary="Root package",
        children=[node_logger, node_secrets],
    )

    example_log = ProjectExample(
        name="logger",
        description="Logging example",
        good_pattern="logger.info('good')",
        bad_pattern="print('bad')",
    )

    return ProjectIndex(
        version="1.0",
        project_name="chutils",
        root=root_node,
        examples=[example_log],
    )


def test_extract_keywords():
    """Проверяет правильность извлечения ключевых слов."""
    task = "Настройка логирования и получение секретов для приложения"
    keywords = extract_keywords(task)
    assert "логирования" in keywords
    assert "получение" in keywords
    assert "секретов" in keywords
    assert "приложения" in keywords
    assert "для" not in keywords
    assert "и" not in keywords


def test_score_node(sample_index):
    """Проверяет корректность расчета весов релевантности для узлов."""
    node = sample_index.root.children[0]  # logger
    # Ключевое слово в имени модуля
    score_name = score_node(node, ["logger"])
    assert score_name > 0

    # Ключевое слово в docstring символа
    score_doc = score_node(node, ["testing"])
    assert score_doc > 0


def test_filter_node_by_modules(sample_index):
    """Проверяет фильтрацию дерева по списку модулей."""
    root = sample_index.root
    # Фильтруем, оставляя только logger
    filtered = filter_node_by_modules(root, ["logger"])
    assert filtered is not None
    assert len(filtered.children) == 1
    assert filtered.children[0].name == "logger"


def test_filter_symbols_by_layer(sample_index):
    """Проверяет фильтрацию символов по уровню доступа/слою."""
    logger_node = sample_index.root.children[0]
    # Только public
    filtered_public = filter_symbols_by_layer(logger_node, {"public"})
    assert len(filtered_public.symbols) == 1
    assert filtered_public.symbols[0].name == "public_func"

    # Public + internal
    filtered_internal = filter_symbols_by_layer(logger_node, {"public", "internal"})
    assert len(filtered_internal.symbols) == 2


def test_filter_examples():
    """Проверяет фильтрацию few-shot примеров."""
    examples = [
        ProjectExample(
            name="logging_example",
            description="Use rich logger",
            good_pattern="good",
            bad_pattern="bad",
        ),
        ProjectExample(
            name="secrets_example",
            description="Use secret manager",
            good_pattern="good",
            bad_pattern="bad",
        ),
    ]

    # Фильтр по модулю
    filtered_by_mod = filter_examples(examples, ["logging_example"], None)
    assert len(filtered_by_mod) == 1
    assert filtered_by_mod[0].name == "logging_example"

    # Фильтр по ключевому слову
    filtered_by_kw = filter_examples(examples, None, ["manager"])
    assert len(filtered_by_kw) == 1
    assert filtered_by_kw[0].name == "secrets_example"


def test_collect_context_slice(mocker, sample_index):
    """Проверяет сборку контекстного среза."""
    mocker.patch("chutils.dev.ast_indexer.Indexer.index", return_value=sample_index)

    # Собираем срез
    markdown = collect_context_slice(
        project_path=Path("."),
        modules=["logger"],
        task=None,
        layer="internal",
    )

    assert "# Контекстный срез для ИИ-ассистента" in markdown
    assert "public_func" in markdown
    assert "internal_func" in markdown
    assert "infra_func" not in markdown  # Узел secret_manager отфильтрован
    assert "Few-Shot Примеры" in markdown


def test_collect_context_slice_by_task(mocker, sample_index):
    """Проверяет сборку контекстного среза по описанию задачи (task)."""
    mocker.patch("chutils.dev.ast_indexer.Indexer.index", return_value=sample_index)

    markdown = collect_context_slice(
        project_path=Path("."),
        modules=None,
        task="logging and debugging helpers",
        layer="public",
    )
    assert "logger" in markdown
    assert "public_func" in markdown


def test_run_interactive_menu_numbers(mocker, sample_index):
    """Проверяет интерактивный выбор модулей по номерам."""
    mocker.patch("chutils.dev.ast_indexer.Indexer.index", return_value=sample_index)
    mocker.patch("builtins.input", return_value="1,2")
    mocker.patch("chutils.dev.chat_context.get_console")

    from chutils.dev.chat_context import run_interactive_menu

    selected = run_interactive_menu(Path("."))
    assert len(selected) == 2
    assert "logger" in selected
    assert "secret_manager" in selected


def test_run_interactive_menu_search(mocker, sample_index):
    """Проверяет интерактивный выбор по ключевому слову поиска."""
    mocker.patch("chutils.dev.ast_indexer.Indexer.index", return_value=sample_index)
    mocker.patch("builtins.input", return_value="logger")
    mocker.patch("chutils.dev.chat_context.get_console")

    from chutils.dev.chat_context import run_interactive_menu

    selected = run_interactive_menu(Path("."))
    assert selected == ["logger"]


def test_run_interactive_menu_cancel(mocker, sample_index):
    """Проверяет отмену интерактивного выбора."""
    mocker.patch("chutils.dev.ast_indexer.Indexer.index", return_value=sample_index)
    mocker.patch("builtins.input", side_effect=KeyboardInterrupt)
    mocker.patch("chutils.dev.chat_context.get_console")

    from chutils.dev.chat_context import run_interactive_menu

    selected = run_interactive_menu(Path("."))
    assert selected == []


def test_run_interactive_menu_empty(mocker, sample_index):
    """Проверяет пустой ввод в интерактивном меню."""
    mocker.patch("chutils.dev.ast_indexer.Indexer.index", return_value=sample_index)
    mocker.patch("builtins.input", return_value="")
    mocker.patch("chutils.dev.chat_context.get_console")

    from chutils.dev.chat_context import run_interactive_menu

    selected = run_interactive_menu(Path("."))
    assert selected == []


def test_run_interactive_menu_search_no_results(mocker, sample_index):
    """Проверяет поиск в интерактивном меню без результатов."""
    mocker.patch("chutils.dev.ast_indexer.Indexer.index", return_value=sample_index)
    mocker.patch("builtins.input", return_value="unrelated_term")
    mocker.patch("chutils.dev.chat_context.get_console")

    from chutils.dev.chat_context import run_interactive_menu

    selected = run_interactive_menu(Path("."))
    assert selected == []
