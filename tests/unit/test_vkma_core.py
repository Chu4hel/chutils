"""Тесты ядра chutils.vkma (валидация HMAC-SHA256, парсинг, модели)."""

import base64
import hashlib
import hmac
import time
import urllib.parse
import pytest

from chutils.vkma import (
    VKMALaunchParams,
    VKMAValidationError,
    parse_vkma_launch_params,
    validate_vkma_launch_params,
)


def generate_vk_sign(params: dict[str, str], client_secret: str) -> str:
    """Вспомогательная функция для генерации валидной подписи VKMA."""
    vk_params = {k: v for k, v in params.items() if k.startswith("vk_")}
    ordered_keys = sorted(vk_params.keys())
    ordered_pairs = [(k, vk_params[k]) for k in ordered_keys]
    query_string = urllib.parse.urlencode(ordered_pairs)

    hash_code = hmac.new(
        client_secret.encode("utf-8"),
        msg=query_string.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()

    return base64.b64encode(hash_code).decode("utf-8").rstrip("=").replace("+", "-").replace("/", "_")


SECRET = "my_secret_key_12345"


def test_validate_vkma_launch_params_valid():
    params = {
        "vk_user_id": "123456",
        "vk_app_id": "7890",
        "vk_is_app_user": "1",
        "vk_language": "ru",
        "vk_ref": "other",
        "vk_ts": str(int(time.time())),
    }
    sign = generate_vk_sign(params, SECRET)
    params["sign"] = sign

    assert validate_vkma_launch_params(params, client_secret=SECRET) is True


def test_parse_vkma_launch_params_query_string():
    params = {
        "vk_user_id": "99999",
        "vk_app_id": "1111",
        "vk_is_app_user": "0",
        "vk_language": "en",
        "vk_platform": "mobile_android",
        "vk_ts": str(int(time.time())),
    }
    sign = generate_vk_sign(params, SECRET)
    params["sign"] = sign
    query_str = "https://example.com/app?" + urllib.parse.urlencode(params)

    model = parse_vkma_launch_params(query_str, client_secret=SECRET)
    assert isinstance(model, VKMALaunchParams)
    assert model.user_id == 99999
    assert model.app_id == 1111
    assert model.is_app_user is False
    assert model.language == "en"
    assert model.platform == "mobile_android"


def test_validate_invalid_sign():
    params = {
        "vk_user_id": "123",
        "vk_app_id": "456",
        "vk_ts": str(int(time.time())),
        "sign": "invalid_signature_str",
    }
    with pytest.raises(VKMAValidationError, match="Недействительная подпись"):
        validate_vkma_launch_params(params, client_secret=SECRET)


def test_validate_expired_ts():
    old_ts = int(time.time()) - 3600
    params = {
        "vk_user_id": "123",
        "vk_app_id": "456",
        "vk_ts": str(old_ts),
    }
    sign = generate_vk_sign(params, SECRET)
    params["sign"] = sign

    with pytest.raises(VKMAValidationError, match="Срок действия параметров запуска VKMA истек"):
        validate_vkma_launch_params(params, client_secret=SECRET, max_age_seconds=600)


def test_missing_secret_and_env_fallback(monkeypatch):
    monkeypatch.delenv("VK_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("VK_SECRET_KEY", raising=False)
    monkeypatch.delenv("CH_VK_CLIENT_SECRET", raising=False)

    params = {"vk_user_id": "123", "vk_ts": "1000", "sign": "abc"}
    with pytest.raises(VKMAValidationError, match="Не указан client_secret VK"):
        validate_vkma_launch_params(params, client_secret=None)

    monkeypatch.setenv("VK_CLIENT_SECRET", SECRET)
    sign = generate_vk_sign(params, SECRET)
    params["sign"] = sign
    assert validate_vkma_launch_params(params, client_secret=None) is True
