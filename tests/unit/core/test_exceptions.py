import pytest

from chutils.exceptions import (
    ChutilsException,
    ConfigError,
    ConfigLoadError,
    ConfigParseError,
    SecretError,
    SecretNotFoundError,
    SecretProviderError,
    LoggerConfigurationError,
    WatcherInitializationError,
    OptionalDependencyError,
    CommandError,
    PathTraversalError
)


def test_chutils_exception_no_context():
    exc = ChutilsException("Test message")
    assert str(exc) == "Test message"
    assert exc.message == "Test message"
    assert exc.context == {}
    assert exc.hint is None


def test_chutils_exception_with_context():
    exc = ChutilsException("Test message", key="value", count=5)
    # Порядок в словаре может варьироваться в старых версиях Python, 
    # но в 3.13+ он стабилен. Однако лучше проверять вхождение.
    s = str(exc)
    assert "Test message" in s
    assert "key='value'" in s
    assert "count=5" in s
    assert exc.context == {"key": "value", "count": 5}


def test_chutils_exception_with_hint():
    exc = ChutilsException("Error", hint="Try again")
    assert "Error" in str(exc)
    assert "СОВЕТ: Try again" in str(exc)
    assert exc.hint == "Try again"


def test_exception_hierarchy():
    assert issubclass(ConfigError, ChutilsException)
    assert issubclass(ConfigLoadError, ConfigError)
    assert issubclass(ConfigParseError, ConfigError)

    assert issubclass(SecretError, ChutilsException)
    assert issubclass(SecretNotFoundError, SecretError)
    assert issubclass(SecretProviderError, SecretError)

    assert issubclass(LoggerConfigurationError, ChutilsException)
    assert issubclass(WatcherInitializationError, ChutilsException)
    assert issubclass(OptionalDependencyError, ChutilsException)
    assert issubclass(CommandError, ChutilsException)


def test_path_traversal_error():
    exc = PathTraversalError("Danger", attempted_path="../../etc/passwd", base_path="/app")
    assert "Danger" in str(exc)
    assert "attempted_path='../../etc/passwd'" in str(exc)
    assert "base_path='/app'" in str(exc)
    assert exc.hint is not None


def test_raises_custom_exception():
    with pytest.raises(ConfigLoadError) as excinfo:
        raise ConfigLoadError("Failed to load", path="/tmp/config.yml")

    assert excinfo.value.message == "Failed to load"
    assert excinfo.value.context["path"] == "/tmp/config.yml"
    assert "path='/tmp/config.yml'" in str(excinfo.value)
