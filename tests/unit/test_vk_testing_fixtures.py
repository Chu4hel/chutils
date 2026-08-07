"""Тесты для pytest фикстур и моков chutils.vk.testing."""

import pytest
from chutils.vk.testing import MockVKApi, mock_vk_api_context
from chutils.vk.testing.fixtures import mock_vk_api, vk_launch_params_factory
from chutils.vkma import validate_vkma_launch_params


def test_vk_launch_params_factory_fixture(vk_launch_params_factory):
    params_str = vk_launch_params_factory(user_id=888, secret_key="my_secret")
    assert validate_vkma_launch_params(params_str, client_secret="my_secret") is True


def test_mock_vk_api_fixture(mock_vk_api):
    mock_vk_api.register_response("custom.method", {"result": "success"})

    res1 = mock_vk_api.call("custom.method", foo="bar")
    assert res1 == {"result": "success"}

    res2 = mock_vk_api.call("users.get", user_ids=[999])
    assert res2[0]["id"] == 999

    assert len(mock_vk_api.calls) == 2
    assert mock_vk_api.calls[0] == ("custom.method", {"foo": "bar"})


def test_mock_vk_api_context():
    with mock_vk_api_context() as mock:
        msg_id = mock.call("messages.send", user_id=1, message="hello")
        assert msg_id == 10001
        assert len(mock.calls) == 1
