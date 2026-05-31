import os

import yaml

from chutils.config import get_config, _cm


def test_env_specific_loading(tmp_path, monkeypatch):
    """Тест загрузки конфигурации в зависимости от CH_ENV."""
    # Создаем временную структуру проекта
    project_root = tmp_path / "project"
    project_root.mkdir()

    config_yml = project_root / "config.yml"
    config_prod_yml = project_root / "config.production.yml"
    config_local_yml = project_root / "config.local.yml"

    # Базовый конфиг
    config_yml.write_text(yaml.dump({
        "App": {"name": "BaseApp", "port": 8080},
        "DB": {"host": "localhost"}
    }))

    # Конфиг продакшена
    config_prod_yml.write_text(yaml.dump({
        "App": {"port": 80},
        "DB": {"host": "prod-db"}
    }))

    # Локальный конфиг
    config_local_yml.write_text(yaml.dump({
        "DB": {"host": "local-db"}
    }))

    # Сбрасываем состояние менеджера и заставляем его искать в нашей временной папке
    _cm._reset()
    monkeypatch.chdir(project_root)

    # 1. Тест без CH_ENV (по умолчанию development)
    monkeypatch.delenv("CH_ENV", raising=False)
    config = get_config()
    assert config["App"]["name"] == "BaseApp"
    assert config["App"]["port"] == 8080  # Не перекрыто, так как config.development.yml нет
    assert config["DB"]["host"] == "local-db"  # Перекрыто локальным файлом

    # 2. Тест с CH_ENV=production
    _cm._reset()
    monkeypatch.setenv("CH_ENV", "production")
    config = get_config()
    assert config["App"]["port"] == 80  # Перекрыто продакшеном
    assert config["DB"]["host"] == "local-db"  # Локальный все еще имеет высший приоритет

    # 3. Тест приоритета: ENV > local > env-specific > base
    monkeypatch.setenv("CH_APP_PORT", "9000")
    _cm.clear_cache()
    from chutils.config import get_config_value
    assert get_config_value("App", "port") == "9000"


def test_env_loading_precedence(tmp_path, monkeypatch):
    """Проверка приоритета: local > env > base."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    (project_root / "config.yml").write_text("Key: base")
    (project_root / "config.production.yml").write_text("Key: env")
    (project_root / "config.local.yml").write_text("Key: local")

    _cm._reset()
    monkeypatch.chdir(project_root)
    monkeypatch.setenv("CH_ENV", "production")

    config = get_config()
    assert config["Key"] == "local"

    # Удаляем локальный, должен подхватиться env
    os.remove(project_root / "config.local.yml")
    _cm.clear_cache()
    config = get_config()
    assert config["Key"] == "env"
