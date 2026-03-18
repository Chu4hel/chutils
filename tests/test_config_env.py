import os

from chutils import config


def test_disable_keyring_env_var_true(config_fs):
    """Проверяет, что установка CH_DISABLE_KEYRING_WARNING=true возвращает True."""
    fs, project_root = config_fs
    os.environ["CH_DISABLE_KEYRING_WARNING"] = "true"

    try:
        # Сбрасываем кэш конфигурации
        config._config_loaded = False
        config._config_object = None

        # ACT
        result = config.get_config_boolean("secrets", "disable_keyring", fallback=False)

        # ASSERT
        assert result is True
    finally:
        if "CH_DISABLE_KEYRING_WARNING" in os.environ:
            del os.environ["CH_DISABLE_KEYRING_WARNING"]


def test_disable_keyring_env_var_false(config_fs):
    """Проверяет, что установка CH_DISABLE_KEYRING_WARNING=false возвращает False."""
    fs, project_root = config_fs
    os.environ["CH_DISABLE_KEYRING_WARNING"] = "false"

    try:
        # Сбрасываем кэш конфигурации
        config._config_loaded = False
        config._config_object = None

        # ACT
        result = config.get_config_boolean("secrets", "disable_keyring", fallback=True)

        # ASSERT
        assert result is False
    finally:
        if "CH_DISABLE_KEYRING_WARNING" in os.environ:
            del os.environ["CH_DISABLE_KEYRING_WARNING"]


def test_disable_keyring_config_file(config_fs):
    """Проверяет, что установка disable_keyring в конфиге работает."""
    fs, project_root = config_fs
    content = """
secrets:
  disable_keyring: true
"""
    fs.create_file(project_root / "config.yml", contents=content)
    fs.create_file(project_root / "pyproject.toml", contents="")

    # Сбрасываем кэш конфигурации
    config._config_loaded = False
    config._config_object = None
    config._paths_initialized = False

    # ACT
    result = config.get_config_boolean("secrets", "disable_keyring", fallback=False)

    # ASSERT
    assert result is True


def test_env_priority_over_config(config_fs):
    """Проверяет, что переменная окружения имеет приоритет над конфигом."""
    fs, project_root = config_fs
    # В конфиге True
    content = """
secrets:
  disable_keyring: true
"""
    fs.create_file(project_root / "config.yml", contents=content)
    fs.create_file(project_root / "pyproject.toml", contents="")

    # В переменной False
    os.environ["CH_DISABLE_KEYRING_WARNING"] = "false"

    try:
        # Сбрасываем кэш конфигурации
        config._config_loaded = False
        config._config_object = None
        config._paths_initialized = False

        # ACT
        result = config.get_config_boolean("secrets", "disable_keyring", fallback=True)

        # ASSERT
        assert result is False  # Должно быть False из переменной
    finally:
        if "CH_DISABLE_KEYRING_WARNING" in os.environ:
            del os.environ["CH_DISABLE_KEYRING_WARNING"]
