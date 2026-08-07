"""Интеграционные тесты для FastAPI, Flask и Aiohttp VKMA middleware / decorators."""

import time
import urllib.parse
import pytest

from chutils.vkma import VKMALaunchParams
from test_vkma_core import SECRET, generate_vk_sign

# Проверяем наличие веб-фреймворков
try:
    from fastapi import FastAPI, Depends
    from fastapi.testclient import TestClient
    from chutils.vkma.integrations.fastapi import VKMAAuthMiddleware, get_current_vkma_params
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    from flask import Flask, jsonify, g
    from chutils.vkma.integrations.flask import require_vkma_auth
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

try:
    from aiohttp import web
    from aiohttp.test_utils import TestClient as AioTestClient, TestServer
    from chutils.vkma.integrations.aiohttp import vkma_auth_middleware
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


@pytest.fixture
def vk_valid_query_str() -> str:
    params = {
        "vk_user_id": "777",
        "vk_app_id": "888",
        "vk_is_app_user": "1",
        "vk_language": "ru",
        "vk_ts": str(int(time.time())),
    }
    sign = generate_vk_sign(params, SECRET)
    params["sign"] = sign
    return urllib.parse.urlencode(params)


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI не установлен")
def test_fastapi_vkma_middleware_and_dependency(vk_valid_query_str):
    app = FastAPI()
    app.add_middleware(VKMAAuthMiddleware, client_secret=SECRET, exclude_paths=["/public"])

    @app.get("/public")
    def public_route():
        return {"status": "ok"}

    @app.get("/protected")
    def protected_route(params: VKMALaunchParams = Depends(get_current_vkma_params)):
        return {"user_id": params.user_id, "app_id": params.app_id}

    client = TestClient(app)

    # Public route без авторизации
    r_pub = client.get("/public")
    assert r_pub.status_code == 200

    # Protected без заголовка -> 401
    r_unauth = client.get("/protected")
    assert r_unauth.status_code == 401

    # Protected с валидным Bearer initData
    r_auth = client.get("/protected", headers={"Authorization": f"Bearer {vk_valid_query_str}"})
    assert r_auth.status_code == 200
    assert r_auth.json() == {"user_id": 777, "app_id": 888}


@pytest.mark.skipif(not HAS_FLASK, reason="Flask не установлен")
def test_flask_vkma_decorator(vk_valid_query_str):
    app = Flask(__name__)

    @app.route("/api/user")
    @require_vkma_auth(client_secret=SECRET)
    def user_info():
        params: VKMALaunchParams = g.vkma_params
        return jsonify({"user_id": params.user_id})

    client = app.test_client()

    # Запрос без авторизации
    res1 = client.get("/api/user")
    assert res1.status_code == 401

    # Запрос с валидной query string
    res2 = client.get(f"/api/user?{vk_valid_query_str}")
    assert res2.status_code == 200
    assert res2.get_json() == {"user_id": 777}


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_AIOHTTP, reason="Aiohttp не установлен")
async def test_aiohttp_vkma_middleware(vk_valid_query_str, aiohttp_client):
    async def handler(request):
        params: VKMALaunchParams = request["vkma_params"]
        return web.json_response({"user_id": params.user_id})

    app = web.Application(middlewares=[vkma_auth_middleware(client_secret=SECRET)])
    app.router.add_get("/aio", handler)

    client = await aiohttp_client(app)

    # Без авторизации
    resp1 = await client.get("/aio")
    assert resp1.status == 401

    # С заголовком X-VKMA-Init-Data
    resp2 = await client.get("/aio", headers={"X-VKMA-Init-Data": vk_valid_query_str})
    assert resp2.status == 200
    data = await resp2.json()
    assert data == {"user_id": 777}
