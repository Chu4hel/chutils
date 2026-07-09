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


def _handle_error(data: dict[str, Any]) -> None:
    """Обрабатывает JSON-ошибки CapMonster и генерирует исключения."""
    error_id = data.get("errorId", 0)
    if error_id == 0:
        return
    error_code = data.get("errorCode", "")
    error_desc = data.get("errorDescription", "")
    msg = f"{error_code}: {error_desc}"

    if "ERROR_ZERO_BALANCE" in error_code:
        raise CaptchaBalanceError(f"Баланс аккаунта CapMonster пуст: {msg}")
    elif "ERROR_KEY_DOES_NOT_EXIST" in error_code or "ERROR_WRONG_USER_KEY" in error_code:
        raise CaptchaServiceError(f"Неверный API-ключ CapMonster: {msg}")
    else:
        raise CaptchaServiceError(f"Ошибка сервиса CapMonster: {msg}")


class CapMonsterSolver(BaseCaptchaSolver):
    """Синхронный клиент для CapMonster Cloud."""
    secret_key_name = "CAPMONSTER_API_KEY"

    def __init__(self, api_key: str | None = None, host: str = "https://api.capmonster.cloud") -> None:
        super().__init__(api_key=api_key)
        self.host = host.rstrip("/")

    def solve_image(
            self,
            image_data: bytes | str,
            timeout: float = 60.0,
            poll_interval: float = 5.0,
            **kwargs: Any,
    ) -> str:
        """Синхронно решает капчу-изображение."""
        img_b64 = image_data if isinstance(image_data, str) else base64.b64encode(image_data).decode("utf-8")

        task = {
            "type": "ImageToTextTask",
            "body": img_b64,
        }
        task.update(kwargs)

        payload = {
            "clientKey": self.api_key,
            "task": task
        }

        with httpx.Client() as client:
            resp = client.post(f"{self.host}/createTask", json=payload)
            data = resp.json()
            _handle_error(data)

            task_id = data["taskId"]

            start_time = time.time()
            while time.time() - start_time < timeout:
                res_resp = client.post(
                    f"{self.host}/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id}
                )
                res_data = res_resp.json()
                _handle_error(res_data)

                if res_data.get("status") == "ready":
                    return str(res_data["solution"]["text"])

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
        """Синхронно решает ReCaptcha v2/v3."""
        task = {
            "type": "RecaptchaV2TaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        }
        task.update(kwargs)

        payload = {
            "clientKey": self.api_key,
            "task": task
        }

        with httpx.Client() as client:
            resp = client.post(f"{self.host}/createTask", json=payload)
            data = resp.json()
            _handle_error(data)

            task_id = data["taskId"]

            start_time = time.time()
            while time.time() - start_time < timeout:
                res_resp = client.post(
                    f"{self.host}/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id}
                )
                res_data = res_resp.json()
                _handle_error(res_data)

                if res_data.get("status") == "ready":
                    return str(res_data["solution"]["gRecaptchaResponse"])

                time.sleep(poll_interval)

            raise CaptchaTimeoutError(f"Превышено время ожидания решения ReCaptcha ({timeout} сек).")


class AsyncCapMonsterSolver(BaseAsyncCaptchaSolver):
    """Асинхронный клиент для CapMonster Cloud."""
    secret_key_name = "CAPMONSTER_API_KEY"

    def __init__(self, api_key: str | None = None, host: str = "https://api.capmonster.cloud") -> None:
        super().__init__(api_key=api_key)
        self.host = host.rstrip("/")

    async def solve_image(
            self,
            image_data: bytes | str,
            timeout: float = 60.0,
            poll_interval: float = 5.0,
            **kwargs: Any,
    ) -> str:
        """Асинхронно решает капчу-изображение."""
        import asyncio

        img_b64 = image_data if isinstance(image_data, str) else base64.b64encode(image_data).decode("utf-8")

        task = {
            "type": "ImageToTextTask",
            "body": img_b64,
        }
        task.update(kwargs)

        payload = {
            "clientKey": self.api_key,
            "task": task
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.host}/createTask", json=payload)
            data = resp.json()
            _handle_error(data)

            task_id = data["taskId"]

            start_time = time.time()
            while time.time() - start_time < timeout:
                res_resp = await client.post(
                    f"{self.host}/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id}
                )
                res_data = res_resp.json()
                _handle_error(res_data)

                if res_data.get("status") == "ready":
                    return str(res_data["solution"]["text"])

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
        """Асинхронно решает ReCaptcha v2/v3."""
        import asyncio

        task = {
            "type": "RecaptchaV2TaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        }
        task.update(kwargs)

        payload = {
            "clientKey": self.api_key,
            "task": task
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.host}/createTask", json=payload)
            data = resp.json()
            _handle_error(data)

            task_id = data["taskId"]

            start_time = time.time()
            while time.time() - start_time < timeout:
                res_resp = await client.post(
                    f"{self.host}/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id}
                )
                res_data = res_resp.json()
                _handle_error(res_data)

                if res_data.get("status") == "ready":
                    return str(res_data["solution"]["gRecaptchaResponse"])

                await asyncio.sleep(poll_interval)

            raise CaptchaTimeoutError(f"Превышено время ожидания решения ReCaptcha ({timeout} сек).")
