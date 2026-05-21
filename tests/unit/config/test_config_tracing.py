from chutils.config import get_config
from chutils.config.manager import _cm


def test_tracing_disabled_by_default(config_fs):
    """Проверяет, что трассировка отключена по умолчанию."""
    assert _cm.tracing_enabled is False
    assert _cm.get_trace() == {}


def test_tracing_records_file_history(config_fs):
    """Проверяет запись истории из файлов."""
    fs, project_root = config_fs

    # Создаем основной конфиг
    config_content = """
    App:
      name: "MyApp"
      version: "1.0"
    """
    fs.create_file(project_root / "config.yml", contents=config_content)

    # Создаем локальный конфиг
    local_content = """
    App:
      version: "1.1-local"
    """
    fs.create_file(project_root / "config.local.yml", contents=local_content)

    # Включаем трассировку
    _cm.tracing_enabled = True

    # Загружаем конфигурацию
    get_config()

    trace = _cm.get_trace()

    # Проверяем историю для App.version
    history = trace.get("app", {}).get("version", [])
    assert len(history) == 2
    assert history[0]["source"].endswith("config.yml")
    assert history[0]["value"] == "1.0"
    assert history[1]["source"].endswith("config.local.yml")
    assert history[1]["value"] == "1.1-local"


def test_tracing_records_env_overrides(config_fs, monkeypatch):
    """Проверяет запись переопределений из переменных окружения."""
    fs, project_root = config_fs

    config_content = """
    DB:
      host: "localhost"
    """
    fs.create_file(project_root / "config.yml", contents=config_content)

    # Устанавливаем переменную окружения
    monkeypatch.setenv("CH_DB_HOST", "prod-db")

    _cm.tracing_enabled = True
    get_config()

    trace = _cm.get_trace()

    history = trace.get("db", {}).get("host", [])
    assert len(history) == 2
    assert history[0]["source"].endswith("config.yml")
    assert history[0]["value"] == "localhost"
    assert history[1]["source"] == "env"
    assert history[1]["value"] == "prod-db"


def test_tracing_reset_on_disable(config_fs):
    """Проверяет очистку данных при отключении трассировки."""
    _cm.tracing_enabled = True
    _cm.record_trace("s", "k", "v", "src")
    assert _cm.get_trace() != {}

    _cm.tracing_enabled = False
    assert _cm.get_trace() == {}
