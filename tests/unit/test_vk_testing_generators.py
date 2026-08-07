"""Тесты генераторов подписей и параметров запуска chutils.vk.testing."""

import pytest
from chutils.vk.testing import generate_fake_init_data, generate_fake_launch_params, generate_fake_user
from chutils.vkma import VKMAValidationError, parse_vkma_launch_params, validate_vkma_launch_params

SECRET = "my_custom_secret_key"


def test_generate_fake_launch_params_valid():
    query_str = generate_fake_launch_params(user_id=777, app_id=888, secret_key=SECRET)
    assert validate_vkma_launch_params(query_str, client_secret=SECRET) is True

    model = parse_vkma_launch_params(query_str, client_secret=SECRET)
    assert model.user_id == 777
    assert model.app_id == 888


def test_generate_fake_launch_params_expired():
    query_str = generate_fake_launch_params(secret_key=SECRET, expired=True)
    with pytest.raises(VKMAValidationError, match="Срок действия параметров запуска VKMA истек"):
        validate_vkma_launch_params(query_str, client_secret=SECRET, max_age_seconds=3600)


def test_generate_fake_launch_params_tampered():
    query_str = generate_fake_launch_params(secret_key=SECRET, tampered=True)
    with pytest.raises(VKMAValidationError, match="Недействительная подпись"):
        validate_vkma_launch_params(query_str, client_secret=SECRET)


def test_generate_fake_init_data():
    init_data = generate_fake_init_data(user_id=555, secret_key=SECRET, extra_params={"platform": "mobile_iphone"})
    model = parse_vkma_launch_params(init_data, client_secret=SECRET)
    assert model.user_id == 555
    assert model.platform == "mobile_iphone"


def test_generate_fake_user():
    user = generate_fake_user(user_id=100, first_name="Пётр", last_name="Петров")
    assert user["id"] == 100
    assert user["first_name"] == "Пётр"
    assert user["last_name"] == "Петров"
