from unittest.mock import patch

import pytest
from chutils.cli import main


def test_cli_suggests_extras_on_missing_dependency(capsys):
    """Тестирует, что CLI выводит рекомендацию по установке при отсутствии pydantic."""

    # Эмулируем вызов chutils dev generate-context --tree
    test_args = ["chutils", "dev", "generate-context", "--tree"]

    # Патчим sys.argv и заставляем has_pydantic вернуть False
    with patch("sys.argv", test_args):
        with patch("chutils.env.has_pydantic", return_value=False):
            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == 1

            captured = capsys.readouterr()
            # Проверяем, что в выводе есть упоминание pydantic и команда установки
            # Ошибки теперь идут в stderr
            output = captured.err or captured.out
            assert "Pydantic is required" in output
            assert "pip install chutils[pydantic]" in output
            assert "ОШИБКА" in output


if __name__ == "__main__":
    pytest.main([__file__])
