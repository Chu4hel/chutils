import base64
import time
from typing import Any

import httpx

from .base import BaseCaptchaSolver, BaseAsyncCaptchaSolver
from .exceptions import (
    CaptchaBalanceError,
    CaptchaServiceError,
    CaptchaTimeoutError,
)


def _handle_error(response_text: str) -> None:
    """Обрабатывает текстовые ошибки RuCaptcha и генерирует исключения."""
    if "ERROR_ZERO_BALANCE" in response_text:
        raise CaptchaBalanceError("Баланс аккаунта RuCaptcha равен нулю или недостаточен.")
    elif "ERROR_WRONG_USER_KEY" in response_text or "ERROR_KEY_DOES_NOT_EXIST" in response_text:
        raise CaptchaServiceError(f"Неверный API-ключ пользователя RuCaptcha: {response_text}")
    else:
        raise CaptchaServiceError(f"Ошибка сервиса RuCaptcha: {response_text}")


class RuCaptchaSolver(BaseCaptchaSolver):
    """Синхронный клиент для RuCaptcha / 2Captcha."""
    secret_key_name = "RUCAPTCHA_API_KEY"

    def __init__(self, api_key: str | None = None, host: str = "https://rucaptcha.com") -> None:
        """Инициализирует RuCaptchaSolver.

        Args:
            api_key: Явно заданный API-ключ.
            host: Адрес API-сервиса RuCaptcha.
        """
        # Также проверяем TWOCAPTCHA_API_KEY как альтернативу
        if not api_key:
            from chutils.secret_manager import SecretManager
            try:
                sm = SecretManager("")
                api_key = sm.get_secret("TWOCAPTCHA_API_KEY")
            except Exception:
                pass
        super().__init__(api_key=api_key)
        self.host = host.rstrip("/")

    def solve_image(
            self,
            image_data: bytes | str,
            timeout: float = 60.0,
            poll_interval: float = 5.0,
            **kwargs: Any,
    ) -> str:
        """Синхронно решает капчу-изображение.

        Args:
            image_data: Бинарные данные картинки или base64-строка.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса решения (в секундах).
            **kwargs: Дополнительные параметры задачи.

        Returns:
            Распознанный текст с изображения.
        """
        # 1. Отправка капчи
        img_b64 = image_data if isinstance(image_data, str) else base64.b64encode(image_data).decode("utf-8")

        payload = {
            "key": self.api_key,
            "method": "base64",
            "body": img_b64,
            "json": 1,
        }
        payload.update(kwargs)

        with httpx.Client() as client:
            resp = client.post(f"{self.host}/in.php", data=payload)
            data = resp.json()

            if data.get("status") != 1:
                _handle_error(data.get("request", ""))

            task_id = data["request"]

            # 2. Опрос результата
            start_time = time.time()
            while time.time() - start_time < timeout:
                res_resp = client.get(
                    f"{self.host}/res.php",
                    params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
                )
                res_data = res_resp.json()

                if res_data.get("status") == 1:
                    return str(res_data["request"])

                request_val = res_data.get("request", "")
                if request_val != "CAPCHA_NOT_READY":
                    _handle_error(request_val)

                time.sleep(poll_interval)

            raise CaptchaTimeoutError(f"Превышено время ожидания решения капчи ({timeout} сек).")

    def solve_recaptcha(
            self,
            sitekey: str,
            page_url: str,
            timeout: float = 120.0,
            poll_interval: float = 5.0,
            **kwargs: Any,
    ) -> str:
        """Синхронно решает ReCaptcha v2/v3.

        Args:
            sitekey: Ключ рекапчи на целевом сайте.
            page_url: URL страницы, на которой расположена рекапча.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса решения (в секундах).
            **kwargs: Дополнительные параметры задачи.

        Returns:
            Токен ответа рекапчи.
        """
        payload = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": page_url,
            "json": 1,
        }
        payload.update(kwargs)

        with httpx.Client() as client:
            resp = client.post(f"{self.host}/in.php", data=payload)
            data = resp.json()

            if data.get("status") != 1:
                _handle_error(data.get("request", ""))

            task_id = data["request"]

            start_time = time.time()
            while time.time() - start_time < timeout:
                res_resp = client.get(
                    f"{self.host}/res.php",
                    params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
                )
                res_data = res_resp.json()

                if res_data.get("status") == 1:
                    return str(res_data["request"])

                request_val = res_data.get("request", "")
                if request_val != "CAPCHA_NOT_READY":
                    _handle_error(request_val)

                time.sleep(poll_interval)

            raise CaptchaTimeoutError(f"Превышено время ожидания решения ReCaptcha ({timeout} сек).")


class AsyncRuCaptchaSolver(BaseAsyncCaptchaSolver):
    """Асинхронный клиент для RuCaptcha / 2Captcha."""
    secret_key_name = "RUCAPTCHA_API_KEY"

    def __init__(self, api_key: str | None = None, host: str = "https://rucaptcha.com") -> None:
        """Инициализирует AsyncRuCaptchaSolver.

        Args:
            api_key: Явно заданный API-ключ.
            host: Адрес API-сервиса RuCaptcha.
        """
        if not api_key:
            from chutils.secret_manager import SecretManager
            try:
                sm = SecretManager("")
                api_key = sm.get_secret("TWOCAPTCHA_API_KEY")
            except Exception:
                pass
        super().__init__(api_key=api_key)
        self.host = host.rstrip("/")

    async def solve_image(
            self,
            image_data: bytes | str,
            timeout: float = 60.0,
            poll_interval: float = 5.0,
            **kwargs: Any,
    ) -> str:
        """Асинхронно решает капчу-изображение.

        Args:
            image_data: Бинарные данные картинки или base64-строка.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса решения (в секундах).
            **kwargs: Дополнительные параметры задачи.

        Returns:
            Распознанный текст с изображения.
        """
        import asyncio

        img_b64 = image_data if isinstance(image_data, str) else base64.b64encode(image_data).decode("utf-8")

        payload = {
            "key": self.api_key,
            "method": "base64",
            "body": img_b64,
            "json": 1,
        }
        payload.update(kwargs)

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.host}/in.php", data=payload)
            data = resp.json()

            if data.get("status") != 1:
                _handle_error(data.get("request", ""))

            task_id = data["request"]

            start_time = time.time()
            while time.time() - start_time < timeout:
                res_resp = await client.get(
                    f"{self.host}/res.php",
                    params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
                )
                res_data = res_resp.json()

                if res_data.get("status") == 1:
                    return str(res_data["request"])

                request_val = res_data.get("request", "")
                if request_val != "CAPCHA_NOT_READY":
                    _handle_error(request_val)

                await asyncio.sleep(poll_interval)

            raise CaptchaTimeoutError(f"Превышено время ожидания решения капчи ({timeout} сек).")

    async def solve_recaptcha(
            self,
            sitekey: str,
            page_url: str,
            timeout: float = 120.0,
            poll_interval: float = 5.0,
            **kwargs: Any,
    ) -> str:
        """Асинхронно решает ReCaptcha v2/v3.

        Args:
            sitekey: Ключ рекапчи на целевом сайте.
            page_url: URL страницы, на которой расположена рекапча.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса решения (в секундах).
            **kwargs: Дополнительные параметры задачи.

        Returns:
            Токен ответа рекапчи.
        """
        import asyncio

        payload = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": page_url,
            "json": 1,
        }
        payload.update(kwargs)

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.host}/in.php", data=payload)
            data = resp.json()

            if data.get("status") != 1:
                _handle_error(data.get("request", ""))

            task_id = data["request"]

            start_time = time.time()
            while time.time() - start_time < timeout:
                res_resp = await client.get(
                    f"{self.host}/res.php",
                    params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
                )
                res_data = res_resp.json()

                if res_data.get("status") == 1:
                    return str(res_data["request"])

                request_val = res_data.get("request", "")
                if request_val != "CAPCHA_NOT_READY":
                    _handle_error(request_val)

                await asyncio.sleep(poll_interval)

            raise CaptchaTimeoutError(f"Превышено время ожидания решения ReCaptcha ({timeout} сек).")
