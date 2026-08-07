"""Логика проверки подписи и парсинга параметров запуска VK Mini Apps."""

import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any

from chutils.vkma.exceptions import VKMAValidationError
from chutils.vkma.models import VKMALaunchParams


def _get_client_secret(provided_secret: str | None) -> str:
    """Извлекает client_secret VK из переданного аргумента, secret_manager или переменных окружения."""
    if provided_secret:
        return provided_secret

    # Пытаемся извлечь через chutils.secret_manager / config / env
    try:
        from chutils.secret_manager import SecretManager
        sm = SecretManager()
        for secret_name in ("vk_client_secret", "vk_secret_key", "CH_VK_CLIENT_SECRET"):
            secret_val = sm.get_secret(secret_name)
            if secret_val:
                return secret_val
    except Exception:
        pass

    import os
    for env_name in ("VK_CLIENT_SECRET", "VK_SECRET_KEY", "CH_VK_CLIENT_SECRET"):
        env_val = os.getenv(env_name)  # chutils: ignore[ChutilsIntegrationRule]
        if env_val:
            return env_val

    raise VKMAValidationError(
        "Не указан client_secret VK и не найден в secret_manager/env.",
        hint="Передайте client_secret явным образом или установите переменную VK_CLIENT_SECRET."
    )


def _extract_vk_params_and_sign(raw_query: str | dict[str, Any]) -> tuple[dict[str, str], str]:
    """Извлекает отсортированные параметры vk_* и подпись sign из query-строки или словаря."""
    params_dict: dict[str, str] = {}

    if isinstance(raw_query, str):
        # Если передан URL или query-строка
        if "?" in raw_query:
            raw_query = raw_query.split("?", 1)[1]
        parsed = urllib.parse.parse_qs(raw_query, keep_blank_values=True)
        for k, v in parsed.items():
            if v:
                params_dict[k] = v[0]
    elif isinstance(raw_query, dict):
        for k, v in raw_query.items():
            params_dict[str(k)] = str(v)
    else:
        raise VKMAValidationError(
            f"Неподдерживаемый тип raw_query: {type(raw_query).__name__}. Ожидался str или dict.",
            hint="Передайте query-строку запуска VKMA или словарь параметров."
        )

    sign = params_dict.get("sign")
    if not sign:
        raise VKMAValidationError(
            "Отсутствует обязательный параметр подписи 'sign' в параметрах VKMA.",
            hint="Убедитесь, что переданы все параметры запуска, включая 'sign'."
        )

    # Фильтруем только параметры, начинающиеся с vk_
    vk_params = {k: v for k, v in params_dict.items() if k.startswith("vk_")}
    return vk_params, sign


def validate_vkma_launch_params(
    raw_query: str | dict[str, Any],
    client_secret: str | None = None,
    max_age_seconds: int | None = None,
) -> bool:
    """Проверяет HMAC-SHA256 подпись VK Mini App launchParams.

    Args:
        raw_query: Строка параметров URL / initData или словарь параметров.
        client_secret: Защищенный ключ приложения VK. Если None, ищется автоматически.
        max_age_seconds: Максимальное время жизни подписи в секундах (по vk_ts).

    Returns:
        True, если подпись валидна и время жизни не истекло.

    Raises:
        VKMAValidationError: Выбрасывается при любой ошибке (подделана или неверна подпись, истек срок действия vk_ts
            или не хватает параметров). Всегда оборачивайте вызов в except VKMAValidationError.
    """
    secret = _get_client_secret(client_secret)
    vk_params, sign = _extract_vk_params_and_sign(raw_query)

    # Проверка времени жизни (max_age_seconds)
    if max_age_seconds is not None:
        vk_ts_str = vk_params.get("vk_ts")
        if not vk_ts_str:
            raise VKMAValidationError("Отсутствует обязательный параметр 'vk_ts' в launchParams.")
        try:
            vk_ts = int(vk_ts_str)
        except ValueError as exc:
            raise VKMAValidationError(f"Некорректный формат vk_ts: {vk_ts_str!r}.") from exc

        now = int(time.time())
        if now - vk_ts > max_age_seconds:
            raise VKMAValidationError(
                f"Срок действия параметров запуска VKMA истек (возраст: {now - vk_ts}с, лимит: {max_age_seconds}с).",
                hint="Запросите новый initData / launchParams с клиента VK Mini App."
            )

    # Алгоритм подписи VK:
    # 1. Отсортировать ключи vk_* по алфавиту.
    # 2. Сформировать query string "key=value&key2=value2...".
    # 3. Посчитать HMAC-SHA256 хеш от полученной строки с ключом client_secret.
    # 4. Кодировать в base64 urlsafe, обрезать `=` и проверить с sign.
    ordered_keys = sorted(vk_params.keys())
    ordered_pairs = [(k, vk_params[k]) for k in ordered_keys]
    query_string = urllib.parse.urlencode(ordered_pairs)

    hash_code = hmac.new(
        secret.encode("utf-8"),
        msg=query_string.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()

    expected_sign = base64.b64encode(hash_code).decode("utf-8").rstrip("=").replace("+", "-").replace("/", "_")

    if not hmac.compare_digest(expected_sign, sign):
        raise VKMAValidationError(
            "Недействительная подпись (HMAC-SHA256) параметров запуска VKMA.",
            hint="Проверьте правильность client_secret и целостность параметров launchParams."
        )

    return True


def parse_vkma_launch_params(
    raw_query: str | dict[str, Any],
    client_secret: str | None = None,
    max_age_seconds: int | None = None,
) -> VKMALaunchParams:
    """Валидирует подпись и парсит query-строку/словарь в модель VKMALaunchParams.

    Args:
        raw_query: Строка URL/initData или словарь с параметрами.
        client_secret: Защищенный ключ приложения VK.
        max_age_seconds: Максимальный допустимый возраст подписи.

    Returns:
        Экземпляр VKMALaunchParams.
    """
    validate_vkma_launch_params(raw_query, client_secret=client_secret, max_age_seconds=max_age_seconds)

    if isinstance(raw_query, str):
        if "?" in raw_query:
            raw_query = raw_query.split("?", 1)[1]
        parsed = urllib.parse.parse_qs(raw_query, keep_blank_values=True)
        data = {k: v[0] for k, v in parsed.items() if v}
    else:
        data = dict(raw_query)

    try:
        return VKMALaunchParams.model_validate(data)
    except Exception as exc:
        raise VKMAValidationError(f"Ошибка валидации Pydantic модели VKMALaunchParams: {exc}") from exc
