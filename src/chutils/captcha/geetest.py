from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx  # chutils: ignore[ChutilsIntegrationRule]

from chutils.scraping.captcha.base import BaseAsyncCaptchaSolver, BaseCaptchaSolver
from chutils.scraping.captcha.exceptions import (
    CaptchaBalanceError,
    CaptchaServiceError,
    CaptchaTimeoutError,
)

from .models import GeeTestResult, GeeTestTaskConfig


def _handle_rucaptcha_error(response_text: str) -> None:
    """Обрабатывает текстовые ошибки RuCaptcha / 2Captcha."""
    if "ERROR_ZERO_BALANCE" in response_text:
        raise CaptchaBalanceError(
            "Баланс аккаунта RuCaptcha/2Captcha равен нулю или недостаточен."
        )
    elif (
        "ERROR_WRONG_USER_KEY" in response_text
        or "ERROR_KEY_DOES_NOT_EXIST" in response_text
    ):
        raise CaptchaServiceError(
            f"Неверный API-ключ RuCaptcha/2Captcha: {response_text}"
        )
    raise CaptchaServiceError(f"Ошибка сервиса RuCaptcha/2Captcha: {response_text}")


def _handle_capmonster_error(data: dict[str, Any]) -> None:
    """Обрабатывает JSON-ошибки CapMonster."""
    error_id = data.get("errorId", 0)
    if error_id == 0:
        return
    error_code = str(data.get("errorCode", ""))
    error_desc = str(data.get("errorDescription", ""))
    msg = f"{error_code}: {error_desc}"

    if "ERROR_ZERO_BALANCE" in error_code:
        raise CaptchaBalanceError(f"Баланс аккаунта CapMonster пуст: {msg}")
    elif (
        "ERROR_KEY_DOES_NOT_EXIST" in error_code or "ERROR_WRONG_USER_KEY" in error_code
    ):
        raise CaptchaServiceError(f"Неверный API-ключ CapMonster: {msg}")
    raise CaptchaServiceError(f"Ошибка сервиса CapMonster: {msg}")


def _parse_geetest_result(raw_result: Any, captcha_id: str) -> GeeTestResult:
    """Преобразует ответ провайдера в структурированный GeeTestResult."""
    if isinstance(raw_result, str):
        try:
            data = json.loads(raw_result)
        except json.JSONDecodeError:
            raise CaptchaServiceError(
                f"Не удалось распарсить ответ решения GeeTest: {raw_result}"
            )
    elif isinstance(raw_result, dict):
        data = raw_result
    else:
        raise CaptchaServiceError(
            f"Неожиданный формат ответа GeeTest: {type(raw_result).__name__}"
        )

    return GeeTestResult(
        lot_number=str(data.get("lot_number", "")),
        pass_token=str(data.get("pass_token", "")),
        gen_time=str(data.get("gen_time", "")),
        captcha_output=str(data.get("captcha_output", "")),
        captcha_id=captcha_id,
    )


class GeeTestSolver(BaseCaptchaSolver):
    """Синхронный и асинхронный клиент для решения GeeTest v4 / v3.

    Поддерживает провайдеры RuCaptcha, 2Captcha и CapMonster Cloud.
    """

    secret_key_name = "RUCAPTCHA_API_KEY"

    def __init__(
        self,
        api_key: str | None = None,
        provider: str = "rucaptcha",
        host: str | None = None,
    ) -> None:
        """Инициализирует GeeTestSolver.

        Args:
            api_key: Явно заданный API-ключ провайдера.
            provider: Имя провайдера ('rucaptcha', '2captcha', 'capmonster').
            host: Пользовательский базовый URL API провайдера.
        """
        self.provider = provider.lower()
        if not api_key:
            from chutils.secret_manager import SecretManager

            try:
                sm = SecretManager("")
                if self.provider == "capmonster":
                    api_key = sm.get_secret("CAPMONSTER_API_KEY")
                elif self.provider == "2captcha":
                    api_key = sm.get_secret("TWOCAPTCHA_API_KEY") or sm.get_secret(
                        "RUCAPTCHA_API_KEY"
                    )
                else:
                    api_key = sm.get_secret("RUCAPTCHA_API_KEY") or sm.get_secret(
                        "TWOCAPTCHA_API_KEY"
                    )
            except Exception:
                pass

        super().__init__(api_key=api_key)

        if host:
            self.host = host.rstrip("/")
        elif self.provider == "capmonster":
            self.host = "https://api.capmonster.cloud"
        elif self.provider == "2captcha":
            self.host = "https://2captcha.com"
        else:
            self.host = "https://rucaptcha.com"

    def _prepare_config(
        self,
        config: GeeTestTaskConfig | None = None,
        captcha_id: str | None = None,
        page_url: str | None = None,
        challenge: str | None = None,
        risk_type: str | None = None,
        api_server: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
    ) -> GeeTestTaskConfig:
        if config is not None:
            return config
        if not captcha_id or not page_url:
            raise ValueError("Необходимо указать captcha_id и page_url.")
        return GeeTestTaskConfig(
            captcha_id=captcha_id,
            page_url=page_url,
            challenge=challenge,
            risk_type=risk_type,
            api_server=api_server,
            user_agent=user_agent,
            proxy=proxy,
        )

    def solve(
        self,
        config: GeeTestTaskConfig | None = None,
        *,
        captcha_id: str | None = None,
        page_url: str | None = None,
        challenge: str | None = None,
        risk_type: str | None = None,
        api_server: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> GeeTestResult:
        """Синхронно решает капчу GeeTest v4 / v3.

        Args:
            config: Конфигурация задачи GeeTestTaskConfig.
            captcha_id: ID капчи (если не передан config).
            page_url: URL страницы (если не передан config).
            challenge: Токен челленджа для v3.
            risk_type: Тип проверки/риска.
            api_server: Домен сервера GeeTest.
            user_agent: User-Agent.
            proxy: Прокси для решения.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса (в секундах).

        Returns:
            Структурированный результат решения GeeTestResult.
        """
        task_cfg = self._prepare_config(
            config,
            captcha_id,
            page_url,
            challenge,
            risk_type,
            api_server,
            user_agent,
            proxy,
        )

        with httpx.Client() as client:
            if self.provider == "capmonster":
                return self._solve_capmonster(client, task_cfg, timeout, poll_interval)
            return self._solve_rucaptcha(client, task_cfg, timeout, poll_interval)

    async def asolve(
        self,
        config: GeeTestTaskConfig | None = None,
        *,
        captcha_id: str | None = None,
        page_url: str | None = None,
        challenge: str | None = None,
        risk_type: str | None = None,
        api_server: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> GeeTestResult:
        """Асинхронно решает капчу GeeTest v4 / v3.

        Args:
            config: Конфигурация задачи GeeTestTaskConfig.
            captcha_id: ID капчи (если не передан config).
            page_url: URL страницы (если не передан config).
            challenge: Токен челленджа для v3.
            risk_type: Тип проверки/риска.
            api_server: Домен сервера GeeTest.
            user_agent: User-Agent.
            proxy: Прокси для решения.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса (в секундах).

        Returns:
            Структурированный результат решения GeeTestResult.
        """
        task_cfg = self._prepare_config(
            config,
            captcha_id,
            page_url,
            challenge,
            risk_type,
            api_server,
            user_agent,
            proxy,
        )

        async with httpx.AsyncClient() as client:
            if self.provider == "capmonster":
                return await self._asolve_capmonster(
                    client, task_cfg, timeout, poll_interval
                )
            return await self._asolve_rucaptcha(
                client, task_cfg, timeout, poll_interval
            )

    def _solve_rucaptcha(
        self,
        client: httpx.Client,
        cfg: GeeTestTaskConfig,
        timeout: float,
        poll_interval: float,
    ) -> GeeTestResult:
        payload: dict[str, Any] = {
            "key": self.api_key,
            "method": "geetest_v4",
            "captcha_id": cfg.captcha_id,
            "pageurl": cfg.page_url,
            "json": 1,
        }
        if cfg.risk_type:
            payload["risk_type"] = cfg.risk_type
        if cfg.challenge:
            payload["challenge"] = cfg.challenge
        if cfg.api_server:
            payload["api_server"] = cfg.api_server
        if cfg.user_agent:
            payload["userAgent"] = cfg.user_agent
        if cfg.proxy:
            payload["proxy"] = cfg.proxy

        resp = client.post(f"{self.host}/in.php", data=payload)
        data = resp.json()
        if data.get("status") != 1:
            _handle_rucaptcha_error(data.get("request", ""))

        task_id = data["request"]
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise CaptchaTimeoutError(
                    f"Превышено время ожидания решения GeeTest ({timeout}с)"
                )
            time.sleep(poll_interval)
            res_resp = client.get(
                f"{self.host}/res.php",
                params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
            )
            res_data = res_resp.json()
            if res_data.get("status") == 1:
                return _parse_geetest_result(res_data["request"], cfg.captcha_id)
            if res_data.get("request") != "CAPCHA_NOT_READY":
                _handle_rucaptcha_error(res_data.get("request", ""))

    async def _asolve_rucaptcha(
        self,
        client: httpx.AsyncClient,
        cfg: GeeTestTaskConfig,
        timeout: float,
        poll_interval: float,
    ) -> GeeTestResult:
        payload: dict[str, Any] = {
            "key": self.api_key,
            "method": "geetest_v4",
            "captcha_id": cfg.captcha_id,
            "pageurl": cfg.page_url,
            "json": 1,
        }
        if cfg.risk_type:
            payload["risk_type"] = cfg.risk_type
        if cfg.challenge:
            payload["challenge"] = cfg.challenge
        if cfg.api_server:
            payload["api_server"] = cfg.api_server
        if cfg.user_agent:
            payload["userAgent"] = cfg.user_agent
        if cfg.proxy:
            payload["proxy"] = cfg.proxy

        resp = await client.post(f"{self.host}/in.php", data=payload)
        data = resp.json()
        if data.get("status") != 1:
            _handle_rucaptcha_error(data.get("request", ""))

        task_id = data["request"]
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise CaptchaTimeoutError(
                    f"Превышено время ожидания решения GeeTest ({timeout}с)"
                )
            await asyncio.sleep(poll_interval)
            res_resp = await client.get(
                f"{self.host}/res.php",
                params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
            )
            res_data = res_resp.json()
            if res_data.get("status") == 1:
                return _parse_geetest_result(res_data["request"], cfg.captcha_id)
            if res_data.get("request") != "CAPCHA_NOT_READY":
                _handle_rucaptcha_error(res_data.get("request", ""))

    def _solve_capmonster(
        self,
        client: httpx.Client,
        cfg: GeeTestTaskConfig,
        timeout: float,
        poll_interval: float,
    ) -> GeeTestResult:
        task: dict[str, Any] = {
            "type": "GeeTestTaskProxyless" if not cfg.proxy else "GeeTestTask",
            "websiteURL": cfg.page_url,
            "gt": cfg.captcha_id,
            "version": 4,
        }
        if cfg.risk_type:
            task["initParameters"] = {"riskType": cfg.risk_type}
        if cfg.challenge:
            task["challenge"] = cfg.challenge

        resp = client.post(
            f"{self.host}/createTask",
            json={"clientKey": self.api_key, "task": task},
        )
        data = resp.json()
        _handle_capmonster_error(data)

        task_id = data.get("taskId")
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise CaptchaTimeoutError(
                    f"Превышено время ожидания решения GeeTest в CapMonster ({timeout}с)"
                )
            time.sleep(poll_interval)
            res_resp = client.post(
                f"{self.host}/getTaskResult",
                json={"clientKey": self.api_key, "taskId": task_id},
            )
            res_data = res_resp.json()
            _handle_capmonster_error(res_data)
            if res_data.get("status") == "ready":
                solution = res_data.get("solution", {})
                return _parse_geetest_result(solution, cfg.captcha_id)

    async def _asolve_capmonster(
        self,
        client: httpx.AsyncClient,
        cfg: GeeTestTaskConfig,
        timeout: float,
        poll_interval: float,
    ) -> GeeTestResult:
        task: dict[str, Any] = {
            "type": "GeeTestTaskProxyless" if not cfg.proxy else "GeeTestTask",
            "websiteURL": cfg.page_url,
            "gt": cfg.captcha_id,
            "version": 4,
        }
        if cfg.risk_type:
            task["initParameters"] = {"riskType": cfg.risk_type}
        if cfg.challenge:
            task["challenge"] = cfg.challenge

        resp = await client.post(
            f"{self.host}/createTask",
            json={"clientKey": self.api_key, "task": task},
        )
        data = resp.json()
        _handle_capmonster_error(data)

        task_id = data.get("taskId")
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise CaptchaTimeoutError(
                    f"Превышено время ожидания решения GeeTest в CapMonster ({timeout}с)"
                )
            await asyncio.sleep(poll_interval)
            res_resp = await client.post(
                f"{self.host}/getTaskResult",
                json={"clientKey": self.api_key, "taskId": task_id},
            )
            res_data = res_resp.json()
            _handle_capmonster_error(res_data)
            if res_data.get("status") == "ready":
                solution = res_data.get("solution", {})
                return _parse_geetest_result(solution, cfg.captcha_id)


class AsyncGeeTestSolver(BaseAsyncCaptchaSolver):
    """Асинхронный клиент для решения GeeTest v4 / v3."""

    def __init__(
        self,
        api_key: str | None = None,
        provider: str = "rucaptcha",
        host: str | None = None,
    ) -> None:
        super().__init__(api_key=api_key)
        self._sync_solver = GeeTestSolver(
            api_key=self.api_key, provider=provider, host=host
        )

    async def solve(
        self,
        config: GeeTestTaskConfig | None = None,
        *,
        captcha_id: str | None = None,
        page_url: str | None = None,
        challenge: str | None = None,
        risk_type: str | None = None,
        api_server: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> GeeTestResult:
        """Асинхронно решает капчу GeeTest."""
        return await self._sync_solver.asolve(
            config=config,
            captcha_id=captcha_id,
            page_url=page_url,
            challenge=challenge,
            risk_type=risk_type,
            api_server=api_server,
            user_agent=user_agent,
            proxy=proxy,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    async def asolve(
        self,
        config: GeeTestTaskConfig | None = None,
        *,
        captcha_id: str | None = None,
        page_url: str | None = None,
        challenge: str | None = None,
        risk_type: str | None = None,
        api_server: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> GeeTestResult:
        """Алиас для solve."""
        return await self.solve(
            config=config,
            captcha_id=captcha_id,
            page_url=page_url,
            challenge=challenge,
            risk_type=risk_type,
            api_server=api_server,
            user_agent=user_agent,
            proxy=proxy,
            timeout=timeout,
            poll_interval=poll_interval,
        )
