import pytest
import yaml

from chutils import is_feature_enabled, require_feature
from chutils.config.manager import _cm


@pytest.fixture
def features_setup(tmp_path, monkeypatch):
    """Настройка временного окружения для тестов фича-флагов."""
    _cm._reset()
    _cm.base_dir = str(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_boolean_flags(features_setup):
    features_file = features_setup / "features.yml"
    features_file.write_text(yaml.dump({
        "feature_on": True,
        "feature_off": False
    }))
    _cm.features_file_path = str(features_file)

    assert is_feature_enabled("feature_on") is True
    assert is_feature_enabled("feature_off") is False


def test_missing_flag(features_setup):
    features_file = features_setup / "features.yml"
    features_file.write_text(yaml.dump({}))
    _cm.features_file_path = str(features_file)

    assert is_feature_enabled("non_existent") is False


def test_env_strategy(features_setup, monkeypatch):
    features_file = features_setup / "features.yml"
    features_file.write_text(yaml.dump({
        "env_feature": {
            "environments": ["production", "staging"]
        }
    }))
    _cm.features_file_path = str(features_file)

    monkeypatch.setenv("CH_ENV", "production")
    assert is_feature_enabled("env_feature") is True

    monkeypatch.setenv("CH_ENV", "development")
    assert is_feature_enabled("env_feature") is False


def test_rollout_strategy(features_setup):
    features_file = features_setup / "features.yml"
    features_file.write_text(yaml.dump({
        "rollout_feature": {
            "rollout": 50
        }
    }))
    _cm.features_file_path = str(features_file)

    # Эти user_id подобраны так, чтобы один попадал в 50%, а другой нет
    assert is_feature_enabled("rollout_feature", {"user_id": "user1"}) is True
    assert is_feature_enabled("rollout_feature", {"user_id": "user16"}) is False

    # Без контекста должна быть выключена
    assert is_feature_enabled("rollout_feature") is False


def test_fallback_to_main_config(features_setup):
    # Файла features.yml нет
    config_file = features_setup / "config.yml"
    config_file.write_text(yaml.dump({
        "feature_flags": {
            "main_config_feature": True
        }
    }))
    _cm.config_file_path = str(config_file)
    _cm.initialize_paths(lambda x, y: features_setup)

    assert is_feature_enabled("main_config_feature") is True


def test_complex_feature_disabled(features_setup):
    features_file = features_setup / "features.yml"
    features_file.write_text(yaml.dump({
        "disabled_complex": {
            "enabled": False,
            "environments": ["development"]  # Даже если окружение подходит
        }
    }))
    _cm.features_file_path = str(features_file)

    assert is_feature_enabled("disabled_complex") is False


def test_require_feature_decorator(features_setup):
    _cm.set_features({"test_feature": True, "disabled_feature": False})

    @require_feature("test_feature")
    def sync_func():
        return "ok"

    @require_feature("disabled_feature")
    def disabled_func():
        return "ok"

    @require_feature("disabled_feature", fallback=lambda: "fallback")
    def fallback_func():
        return "ok"

    assert sync_func() == "ok"
    assert disabled_func() is None
    assert fallback_func() == "fallback"


@pytest.mark.asyncio
async def test_require_feature_decorator_async(features_setup):
    _cm.set_features({"test_feature": True, "disabled_feature": False})

    @require_feature("test_feature")
    async def async_func():
        return "async_ok"

    @require_feature("disabled_feature")
    async def async_disabled():
        return "async_ok"

    @require_feature("disabled_feature", fallback=lambda: "async_fallback")
    async def async_fallback_func():
        return "async_ok"

    assert await async_func() == "async_ok"
    assert await async_disabled() is None
    assert await async_fallback_func() == "async_fallback"


def test_require_feature_with_context(features_setup):
    _cm.set_features({
        "rollout_feature": {
            "rollout": 50
        }
    })

    @require_feature("rollout_feature")
    def feature_func(context=None):
        return "active"

    assert feature_func(context={"user_id": "user1"}) == "active"
    assert feature_func(context={"user_id": "user16"}) is None
