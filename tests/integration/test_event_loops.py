import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chutils import config
from chutils.config.manager import _cm

# Опциональный импорт uvloop
try:
    import uvloop

    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False


@pytest.fixture(autouse=True)
def setup_fs_config(tmp_path):
    """Инициализация временного файла конфигурации для интеграционных тестов."""
    _cm._reset()
    config_dir = tmp_path / "project"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yml"

    with open(config_path, "w", encoding="utf-8") as f:
        f.write("""
App:
  name: "IntegrationTest"
  version: "2.0"
""")

    # Инициализируем пути в ConfigManager вручную
    _cm.base_dir = str(config_dir)
    _cm.config_file_path = str(config_path)
    _cm.paths_initialized = True
    yield config_path
    _cm._reset()


def test_standard_asyncio_run(setup_fs_config):
    """Проверяет работу асинхронного доступа через стандартный asyncio.run()."""

    async def run_test():
        cfg = await config.aget_config()
        assert cfg["App"]["name"] == "IntegrationTest"

        success = await config.asave_config_value("App", "name", "UpdatedAsyncio")
        assert success is True

        cfg_updated = await config.aget_config()
        assert cfg_updated["App"]["name"] == "UpdatedAsyncio"

    asyncio.run(run_test())


@pytest.mark.skipif(not UVLOOP_AVAILABLE, reason="uvloop доступен только на Linux/macOS")
def test_uvloop_event_loop(setup_fs_config):
    """Проверяет работу асинхронного доступа с использованием uvloop."""

    async def run_test():
        cfg = await config.aget_config()
        assert cfg["App"]["name"] == "IntegrationTest"

        success = await config.asave_config_value("App", "name", "UpdatedUvloop")
        assert success is True

        cfg_updated = await config.aget_config()
        assert cfg_updated["App"]["name"] == "UpdatedUvloop"

    # Устанавливаем uvloop в качестве event loop policy
    old_policy = asyncio.get_event_loop_policy()
    try:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        asyncio.run(run_test())
    finally:
        asyncio.set_event_loop_policy(old_policy)


def test_fastapi_integration(setup_fs_config):
    """Проверяет работу асинхронных функций chutils внутри эндпоинтов FastAPI."""
    app = FastAPI()

    @app.get("/config")
    async def get_app_config():
        cfg = await config.aget_config()
        return {"name": cfg["App"]["name"]}

    @app.post("/config/update")
    async def update_app_config(name: str):
        success = await config.asave_config_value("App", "name", name)
        return {"success": success}

    client = TestClient(app)

    # 1. Читаем конфиг через API
    response = client.get("/config")
    assert response.status_code == 200
    assert response.json() == {"name": "IntegrationTest"}

    # 2. Обновляем конфиг через API
    response = client.post("/config/update?name=FastAPIUpdated")
    assert response.status_code == 200
    assert response.json() == {"success": True}

    # 3. Читаем обновленный конфиг через API
    response = client.get("/config")
    assert response.status_code == 200
    assert response.json() == {"name": "FastAPIUpdated"}
