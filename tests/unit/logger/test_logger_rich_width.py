from chutils.cli_utils import set_console_width, _get_default_width
from chutils.logger import setup_logger
from chutils.testing.fixtures import mock_chutils_config


def test_logger_applies_cli_width(mock_chutils_config):
    """Проверка того, что setup_logger применяет ширину из конфига."""
    # Очищаем состояние
    set_console_width(None)

    # Настраиваем конфиг
    mock_chutils_config.set("CLI", "console_width", 155)

    # При вызове setup_logger ширина должна обновиться
    setup_logger("test_width_logger", force_reconfigure=True)

    assert _get_default_width() == 155


def test_logger_invalid_width_handled(mock_chutils_config):
    """Проверка обработки некорректного значения ширины в конфиге."""
    set_console_width(120)  # Начальное значение

    mock_chutils_config.set("CLI", "console_width", "invalid")

    # Не должно упасть, должно просто проигнорировать
    setup_logger("test_invalid_width", force_reconfigure=True)

    # Значение не должно измениться на 'invalid', 
    # в данном случае оно останется 120, так как set_console_width(int(...)) упадет и поймается
    assert _get_default_width() == 120
