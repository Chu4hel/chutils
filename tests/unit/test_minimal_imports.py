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


def test_env_discovery_resilience():
    """
    Проверяет, что функции обнаружения в chutils.env не падают,
    если родительский пакет отсутствует.
    """
    # Удаляем chutils.env из кэша, чтобы переинициализировать переменные (OTEL_AVAILABLE и др.)
    if 'chutils.env' in sys.modules:
        del sys.modules['chutils.env']

    # Имитируем отсутствие opentelemetry через перехват find_spec
    # Мы не можем просто пропатчить sys.modules для find_spec, так как он лезет глубже
    with patch('importlib.util.find_spec') as mock_find:
        # Настраиваем так, чтобы поиск любого подмодуля opentelemetry вызывал ошибку,
        # имитируя поведение при отсутствии родительского пакета.
        def side_effect(name, package=None):
            if name.startswith('opentelemetry'):
                raise ModuleNotFoundError(f"No module named '{name.split('.')[0]}'")
            return None

        mock_find.side_effect = side_effect

        from chutils import env
        importlib.reload(env)

        assert env.OTEL_AVAILABLE is False
        assert env.is_otel_enabled() is False
