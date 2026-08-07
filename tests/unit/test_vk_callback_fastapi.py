"""Интеграционные тесты VKCallbackRouter с FastAPI TestClient."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chutils.vk.callback import VKCallbackRouter


def test_fastapi_vk_callback_confirmation():
    router = VKCallbackRouter(confirmation_code="secret_code_xyz", secret_key="my_secret_key")

    app = FastAPI()
    app.include_router(router.get_fastapi_router())

    client = TestClient(app)

    # Запрос подтверждения сервера
    res = client.post("/vk-callback", json={"type": "confirmation", "group_id": 1, "secret": "my_secret_key"})
    assert res.status_code == 200
    assert res.text == "secret_code_xyz"


def test_fastapi_vk_callback_invalid_secret():
    router = VKCallbackRouter(confirmation_code="code", secret_key="correct_secret")

    app = FastAPI()
    app.include_router(router.get_fastapi_router())

    client = TestClient(app)

    res = client.post("/vk-callback", json={"type": "message_new", "secret": "wrong_secret"})
    assert res.status_code == 403


def test_fastapi_vk_callback_message_event():
    router = VKCallbackRouter(secret_key="key")
    received_msgs = []

    @router.on_message_new
    def on_msg(data):
        received_msgs.append(data)

    app = FastAPI()
    app.include_router(router.get_fastapi_router())

    client = TestClient(app)

    res = client.post("/vk-callback", json={"type": "message_new", "secret": "key", "object": {"text": "hi"}})
    assert res.status_code == 200
    assert res.text == "ok"
    assert len(received_msgs) == 1
