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
)


def test_chutils_exception_no_context():
    exc = ChutilsException("Test message")
    assert str(exc) == "Test message"
    assert exc.message == "Test message"
    assert exc.context == {}


def test_chutils_exception_with_context():
    exc = ChutilsException("Test message", key="value", count=5)
    assert str(exc) == "Test message [Контекст: key='value', count=5]"
    assert exc.context == {"key": "value", "count": 5}


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


def test_raises_custom_exception():
    with pytest.raises(ConfigLoadError) as excinfo:
        raise ConfigLoadError("Failed to load", path="/tmp/config.yml")

    assert excinfo.value.message == "Failed to load"
    assert excinfo.value.context["path"] == "/tmp/config.yml"
    assert "path='/tmp/config.yml'" in str(excinfo.value)
