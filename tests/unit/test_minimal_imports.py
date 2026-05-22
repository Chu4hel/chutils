import importlib
import sys
from unittest.mock import patch

import pytest


def test_chutils_imports_without_optional_deps():
    """
    Проверяет, что библиотека импортируется и работает (в базовом режиме)
    даже если опциональные зависимости (типа python-json-logger) отсутствуют.
    """

    # Список модулей, которые мы хотим 'спрятать'
    optional_mods = [
        'pythonjsonlogger',
        'pydantic',
        'watchdog',
        'opentelemetry',
        'rich',
        'keyring'
    ]

    # Очищаем кэш импортов для chutils, чтобы форсировать повторную загрузку
    to_delete = [m for m in sys.modules if m.startswith('chutils')]
    for m in to_delete:
        del sys.modules[m]

    with patch.dict(sys.modules, {mod: None for mod in optional_mods}):
        try:
            # Пытаемся импортировать корень
            import chutils
            importlib.reload(chutils)

            # Проверяем доступ к основным ленивым атрибутам
            # Они не должны вызывать ImportError при обращении
            assert chutils.setup_logger is not None
            assert chutils.get_config is not None

            # Попытка вызова setup_logger (должна откатиться к стандартному logging)
            logger = chutils.setup_logger("smoke_test")
            logger.info("Smoke test passed")

        except ImportError as e:
            pytest.fail(f"Библиотека не импортируется без опциональных зависимостей: {e}")
        except Exception as e:
            pytest.fail(f"Ошибка при работе в минимальном окружении: {e}")
