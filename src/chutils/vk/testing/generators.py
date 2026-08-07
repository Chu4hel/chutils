"""Генераторы поддельных подписей, initData и launchParams VK/VKMA для тестов."""

import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any


def _compute_vk_sign(vk_params: dict[str, str], secret_key: str) -> str:
    """Вычисляет валидную HMAC-SHA256 подпись VK по алгоритму VK Mini Apps."""
    ordered_keys = sorted(vk_params.keys())
    ordered_pairs = [(k, vk_params[k]) for k in ordered_keys]
    query_string = urllib.parse.urlencode(ordered_pairs)

    hash_code = hmac.new(
        secret_key.encode("utf-8"),
        msg=query_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    return base64.b64encode(hash_code).decode("utf-8").rstrip("=").replace("+", "-").replace("/", "_")


def generate_fake_launch_params(
    user_id: int = 123456,
    app_id: int = 77777,
    client_secret: str | None = None,
    secret_key: str | None = None,
    expired: bool = False,
    tampered: bool = False,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Генерирует query-строку launchParams VK Mini App с валидной (или поврежденной) HMAC-SHA256 подписью.

    Args:
        user_id: ID фейкового пользователя VK.
        app_id: ID фейкового приложения VK Mini App.
        client_secret: Ключ приложения для подписи HMAC-SHA256 (основное имя параметра).
        secret_key: Псевдоним для client_secret (для обратной совместимости).
        expired: Если True, генерирует устаревший timestamp (vk_ts назад на 24 часа).
        tampered: Если True, подделывает подпись (делает ее недействительной).
        extra_params: Дополнительные параметры (например, vk_platform, vk_language).

    Returns:
        Строка URL query-параметров с ключом `sign`.
    """
    secret = client_secret or secret_key or "test_secret_key"
    ts = int(time.time()) - (86400 if expired else 0)

    params: dict[str, str] = {
        "vk_user_id": str(user_id),
        "vk_app_id": str(app_id),
        "vk_is_app_user": "1",
        "vk_are_notifications_enabled": "0",
        "vk_language": "ru",
        "vk_ref": "other",
        "vk_ts": str(ts),
    }

    if extra_params:
        for k, v in extra_params.items():
            key = k if k.startswith("vk_") else f"vk_{k}"
            params[key] = str(v)

    sign = _compute_vk_sign(params, secret)
    if tampered:
        sign = "tampered_invalid_signature_hash"

    params["sign"] = sign
    return urllib.parse.urlencode(params)


def generate_fake_init_data(
    user_id: int = 123456,
    app_id: int = 77777,
    secret_key: str = "test_secret_key",
    expired: bool = False,
    tampered: bool = False,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Генерирует фейковую подпись и формат initData для использования в заголовке `Authorization: Bearer <initData>`.

    Args:
        user_id: ID фейкового пользователя VK.
        app_id: ID фейкового приложения.
        secret_key: Ключ приложения для подписи.
        expired: Если True, просроченный timestamp.
        tampered: Если True, поврежденная подпись.
        extra_params: Дополнительные параметры.

    Returns:
        Query-строка initData.
    """
    return generate_fake_launch_params(
        user_id=user_id,
        app_id=app_id,
        secret_key=secret_key,
        expired=expired,
        tampered=tampered,
        extra_params=extra_params,
    )


def generate_fake_user(user_id: int = 123456, first_name: str = "Иван", last_name: str = "Иванов") -> dict[str, Any]:
    """Возвращает Pydantic-совместимый словарь с данными пользователя VK API.

    Args:
        user_id: ID пользователя VK.
        first_name: Имя пользователя.
        last_name: Фамилия пользователя.

    Returns:
        Словарь с атрибутами пользователя VK.
    """
    return {
        "id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "can_access_closed": True,
        "is_closed": False,
        "photo_200": f"https://vk.com/images/camera_200.png?id={user_id}",
    }
