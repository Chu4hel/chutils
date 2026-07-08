import importlib
import sys
from unittest.mock import patch

import pytest


def test_web_import_without_httpx() -> None:
    """Проверяет, что при отсутствии библиотеки httpx импорт chutils.web вызывает OptionalDependencyError."""
    # Очищаем кэш импорта для chutils.web
    to_delete = [m for m in sys.modules if m.startswith("chutils.web")]
    for m in to_delete:
        sys.modules.pop(m, None)

    # Имитируем отсутствие httpx
    with patch.dict(sys.modules, {"httpx": None}):
        from chutils.exceptions import OptionalDependencyError

        with pytest.raises(OptionalDependencyError) as exc_info:
            importlib.import_module("chutils.web")

        assert "httpx" in str(exc_info.value)
        assert "chutils[web]" in str(exc_info.value)


def test_web_import_with_httpx() -> None:
    """Проверяет, что при наличии httpx импорт chutils.web проходит успешно."""
    # Очищаем кэш импорта для chutils.web
    to_delete = [m for m in sys.modules if m.startswith("chutils.web")]
    for m in to_delete:
        sys.modules.pop(m, None)

    try:
        web_mod = importlib.import_module("chutils.web")
        assert web_mod.WebClient is not None
        assert web_mod.AsyncWebClient is not None
    except Exception as e:
        pytest.fail(f"Не удалось импортировать chutils.web при наличии httpx: {e}")
