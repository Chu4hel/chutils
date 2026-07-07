"""
Тесты для проверки поведения функций шифрования при отсутствии зависимости cryptography.
"""

from pathlib import Path
import pytest

from chutils import crypto
from chutils.exceptions import OptionalDependencyError


@pytest.fixture
def mock_missing_cryptography(monkeypatch: pytest.MonkeyPatch) -> None:
    """Фикстура для имитации отсутствия библиотеки cryptography."""
    monkeypatch.setattr(crypto, "_HAS_CRYPTOGRAPHY", False)


def test_encrypt_portable_raises_dependency_error(mock_missing_cryptography: None) -> None:
    """Проверяет, что encrypt_portable выбрасывает OptionalDependencyError при отсутствии cryptography."""
    with pytest.raises(OptionalDependencyError) as exc_info:
        crypto.encrypt_portable("data", "seed")
    assert "chutils[crypto]" in str(exc_info.value)


def test_decrypt_portable_raises_dependency_error(mock_missing_cryptography: None) -> None:
    """Проверяет, что decrypt_portable выбрасывает OptionalDependencyError при отсутствии cryptography."""
    with pytest.raises(OptionalDependencyError) as exc_info:
        crypto.decrypt_portable("encrypted", "seed")
    assert "chutils[crypto]" in str(exc_info.value)


def test_encrypt_file_raises_dependency_error(mock_missing_cryptography: None, tmp_path: Path) -> None:
    """Проверяет, что encrypt_file выбрасывает OptionalDependencyError при отсутствии cryptography."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content", encoding="utf-8")
    with pytest.raises(OptionalDependencyError) as exc_info:
        crypto.encrypt_file(test_file, "seed")
    assert "chutils[crypto]" in str(exc_info.value)


def test_decrypt_file_raises_dependency_error(mock_missing_cryptography: None, tmp_path: Path) -> None:
    """Проверяет, что decrypt_file выбрасывает OptionalDependencyError при отсутствии cryptography."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content", encoding="utf-8")
    with pytest.raises(OptionalDependencyError) as exc_info:
        crypto.decrypt_file(test_file, "seed")
    assert "chutils[crypto]" in str(exc_info.value)
