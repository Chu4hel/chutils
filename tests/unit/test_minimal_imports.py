import subprocess
import sys


def test_chutils_imports_without_optional_deps():
    """Проверяет, что библиотека импортируется и работает (в базовом режиме)
    даже если опциональные зависимости (типа python-json-logger) отсутствуют.
    """
    code = """
import sys
from unittest.mock import patch

optional_mods = [
    "pythonjsonlogger",
    "pydantic",
    "watchdog",
    "opentelemetry",
    "rich",
    "keyring",
]

with patch.dict(sys.modules, {mod: None for mod in optional_mods}):
    import chutils
    assert chutils.setup_logger is not None
    assert chutils.get_config is not None
    logger = chutils.setup_logger("smoke_test")
    logger.info("Smoke test passed")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"


def test_env_discovery_resilience():
    """Проверяет, что функции обнаружения в chutils.env не падают,
    если родительский пакет отсутствует.
    """
    code = """
from unittest.mock import patch
import importlib.util

def side_effect(name, package=None):
    if name.startswith("opentelemetry"):
        raise ModuleNotFoundError(f"No module named '{name.split('.')[0]}'")

with patch("importlib.util.find_spec", side_effect=side_effect):
    from chutils import env
    assert env.OTEL_AVAILABLE is False
    assert env.is_otel_enabled() is False
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
