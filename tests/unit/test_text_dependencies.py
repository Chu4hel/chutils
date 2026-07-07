"""
Тесты для проверки поведения функций модуля text при отсутствии зависимости rapidfuzz.
"""

import pytest

from chutils import text
from chutils.exceptions import OptionalDependencyError


@pytest.fixture
def mock_missing_rapidfuzz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Фикстура для имитации отсутствия библиотеки rapidfuzz."""
    monkeypatch.setattr(text, "_HAS_RAPIDFUZZ", False)


def test_is_significant_difference_raises_dependency_error(mock_missing_rapidfuzz: None) -> None:
    """Проверяет, что is_significant_difference выбрасывает OptionalDependencyError при отсутствии rapidfuzz."""
    with pytest.raises(OptionalDependencyError) as exc_info:
        text.is_significant_difference("text1", "text2")
    assert "chutils[text]" in str(exc_info.value)
