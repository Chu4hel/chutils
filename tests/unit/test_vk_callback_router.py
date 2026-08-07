"""Unit-тесты для ядра VKCallbackRouter."""

import pytest
from chutils.vk.callback import VKCallbackError, VKCallbackRouter


@pytest.mark.asyncio
async def test_vk_callback_router_confirmation():
    router = VKCallbackRouter(confirmation_code="conf_code_12345", secret_key="my_secret")

    event = {"type": "confirmation", "group_id": 100, "secret": "my_secret"}
    response = await router.handle_event(event)
    assert response == "conf_code_12345"


@pytest.mark.asyncio
async def test_vk_callback_router_invalid_secret():
    router = VKCallbackRouter(confirmation_code="code", secret_key="expected_secret")

    event = {"type": "message_new", "secret": "wrong_secret"}
    with pytest.raises(VKCallbackError, match="Недействительный секретный ключ"):
        await router.handle_event(event)


@pytest.mark.asyncio
async def test_vk_callback_router_event_handling():
    router = VKCallbackRouter(secret_key="sec")

    handled_events = []

    @router.on_message_new
    def handle_msg(data):
        handled_events.append(data)

    event = {"type": "message_new", "object": {"message": {"text": "hello"}}, "secret": "sec"}
    res = await router.handle_event(event)

    assert res == "ok"
    assert len(handled_events) == 1
    assert handled_events[0]["object"]["message"]["text"] == "hello"
