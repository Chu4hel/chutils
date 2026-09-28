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

from .models import ReCaptchaEnterpriseConfig


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


class ReCaptchaEnterpriseSolver(BaseCaptchaSolver):
    """Синхронный и асинхронный клиент для решения reCAPTCHA Enterprise.

    Поддерживает провайдеры RuCaptcha, 2Captcha и CapMonster Cloud.
    """

    secret_key_name = "RUCAPTCHA_API_KEY"

    def __init__(
        self,
        api_key: str | None = None,
        provider: str = "rucaptcha",
        host: str | None = None,
    ) -> None:
        """Инициализирует ReCaptchaEnterpriseSolver.

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
        config: ReCaptchaEnterpriseConfig | None = None,
        site_key: str | None = None,
        page_url: str | None = None,
        action: str | None = None,
        enterprise_payload: dict[str, str | int | float | bool] | None = None,
        s_token: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        min_score: float | None = None,
    ) -> ReCaptchaEnterpriseConfig:
        if config is not None:
            return config
        if not site_key or not page_url:
            raise ValueError("Необходимо указать site_key и page_url.")
        return ReCaptchaEnterpriseConfig(
            site_key=site_key,
            page_url=page_url,
            action=action,
            enterprise_payload=enterprise_payload,
            s_token=s_token,
            user_agent=user_agent,
            proxy=proxy,
            min_score=min_score,
        )

    def solve(
        self,
        config: ReCaptchaEnterpriseConfig | None = None,
        *,
        site_key: str | None = None,
        page_url: str | None = None,
        action: str | None = None,
        enterprise_payload: dict[str, str | int | float | bool] | None = None,
        s_token: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        min_score: float | None = None,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> str:
        """Синхронно решает капчу reCAPTCHA Enterprise и возвращает токен.

        Args:
            config: Конфигурация задачи ReCaptchaEnterpriseConfig.
            site_key: Sitekey reCAPTCHA Enterprise.
            page_url: URL страницы.
            action: Действие (action).
            enterprise_payload: Полезная нагрузка Enterprise.
            s_token: Защитный токен s_token.
            user_agent: User-Agent.
            proxy: Прокси для решения.
            min_score: Минимальный требуемый score.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса (в секундах).

        Returns:
            Токен решения g-recaptcha-response.
        """
        task_cfg = self._prepare_config(
            config,
            site_key,
            page_url,
            action,
            enterprise_payload,
            s_token,
            user_agent,
            proxy,
            min_score,
        )

        with httpx.Client() as client:
            if self.provider == "capmonster":
                return self._solve_capmonster(client, task_cfg, timeout, poll_interval)
            return self._solve_rucaptcha(client, task_cfg, timeout, poll_interval)

    async def asolve(
        self,
        config: ReCaptchaEnterpriseConfig | None = None,
        *,
        site_key: str | None = None,
        page_url: str | None = None,
        action: str | None = None,
        enterprise_payload: dict[str, str | int | float | bool] | None = None,
        s_token: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        min_score: float | None = None,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> str:
        """Асинхронно решает капчу reCAPTCHA Enterprise и возвращает токен.

        Args:
            config: Конфигурация задачи ReCaptchaEnterpriseConfig.
            site_key: Sitekey reCAPTCHA Enterprise.
            page_url: URL страницы.
            action: Действие (action).
            enterprise_payload: Полезная нагрузка Enterprise.
            s_token: Защитный токен s_token.
            user_agent: User-Agent.
            proxy: Прокси для решения.
            min_score: Минимальный требуемый score.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса (в секундах).

        Returns:
            Токен решения g-recaptcha-response.
        """
        task_cfg = self._prepare_config(
            config,
            site_key,
            page_url,
            action,
            enterprise_payload,
            s_token,
            user_agent,
            proxy,
            min_score,
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
        cfg: ReCaptchaEnterpriseConfig,
        timeout: float,
        poll_interval: float,
    ) -> str:
        payload: dict[str, Any] = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": cfg.site_key,
            "pageurl": cfg.page_url,
            "enterprise": 1,
            "json": 1,
        }
        if cfg.action:
            payload["action"] = cfg.action
        if cfg.s_token:
            payload["data-s"] = cfg.s_token
        if cfg.enterprise_payload:
            payload["enterprise_payload"] = json.dumps(cfg.enterprise_payload)
        if cfg.min_score is not None:
            payload["min_score"] = cfg.min_score
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
                    f"Превышено время ожидания решения reCAPTCHA Enterprise ({timeout}с)"
                )
            time.sleep(poll_interval)
            res_resp = client.get(
                f"{self.host}/res.php",
                params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
            )
            res_data = res_resp.json()
            if res_data.get("status") == 1:
                return str(res_data["request"])
            if res_data.get("request") != "CAPCHA_NOT_READY":
                _handle_rucaptcha_error(res_data.get("request", ""))

    async def _asolve_rucaptcha(
        self,
        client: httpx.AsyncClient,
        cfg: ReCaptchaEnterpriseConfig,
        timeout: float,
        poll_interval: float,
    ) -> str:
        payload: dict[str, Any] = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": cfg.site_key,
            "pageurl": cfg.page_url,
            "enterprise": 1,
            "json": 1,
        }
        if cfg.action:
            payload["action"] = cfg.action
        if cfg.s_token:
            payload["data-s"] = cfg.s_token
        if cfg.enterprise_payload:
            payload["enterprise_payload"] = json.dumps(cfg.enterprise_payload)
        if cfg.min_score is not None:
            payload["min_score"] = cfg.min_score
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
                    f"Превышено время ожидания решения reCAPTCHA Enterprise ({timeout}с)"
                )
            await asyncio.sleep(poll_interval)
            res_resp = await client.get(
                f"{self.host}/res.php",
                params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
            )
            res_data = res_resp.json()
            if res_data.get("status") == 1:
                return str(res_data["request"])
            if res_data.get("request") != "CAPCHA_NOT_READY":
                _handle_rucaptcha_error(res_data.get("request", ""))

    def _solve_capmonster(
        self,
        client: httpx.Client,
        cfg: ReCaptchaEnterpriseConfig,
        timeout: float,
        poll_interval: float,
    ) -> str:
        task: dict[str, Any] = {
            "type": "RecaptchaV2EnterpriseTaskProxyless"
            if not cfg.proxy
            else "RecaptchaV2EnterpriseTask",
            "websiteURL": cfg.page_url,
            "websiteKey": cfg.site_key,
        }
        if cfg.enterprise_payload:
            task["enterprisePayload"] = cfg.enterprise_payload
        if cfg.s_token:
            task["sToken"] = cfg.s_token
        if cfg.action:
            task["action"] = cfg.action

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
                    f"Превышено время ожидания решения reCAPTCHA Enterprise в CapMonster ({timeout}с)"
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
                return str(solution.get("gRecaptchaResponse", ""))

    async def _asolve_capmonster(
        self,
        client: httpx.AsyncClient,
        cfg: ReCaptchaEnterpriseConfig,
        timeout: float,
        poll_interval: float,
    ) -> str:
        task: dict[str, Any] = {
            "type": "RecaptchaV2EnterpriseTaskProxyless"
            if not cfg.proxy
            else "RecaptchaV2EnterpriseTask",
            "websiteURL": cfg.page_url,
            "websiteKey": cfg.site_key,
        }
        if cfg.enterprise_payload:
            task["enterprisePayload"] = cfg.enterprise_payload
        if cfg.s_token:
            task["sToken"] = cfg.s_token
        if cfg.action:
            task["action"] = cfg.action

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
                    f"Превышено время ожидания решения reCAPTCHA Enterprise в CapMonster ({timeout}с)"
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
                return str(solution.get("gRecaptchaResponse", ""))


class AsyncReCaptchaEnterpriseSolver(BaseAsyncCaptchaSolver):
    """Асинхронный клиент для решения reCAPTCHA Enterprise."""

    def __init__(
        self,
        api_key: str | None = None,
        provider: str = "rucaptcha",
        host: str | None = None,
    ) -> None:
        super().__init__(api_key=api_key)
        self._sync_solver = ReCaptchaEnterpriseSolver(
            api_key=self.api_key, provider=provider, host=host
        )

    async def solve(
        self,
        config: ReCaptchaEnterpriseConfig | None = None,
        *,
        site_key: str | None = None,
        page_url: str | None = None,
        action: str | None = None,
        enterprise_payload: dict[str, str | int | float | bool] | None = None,
        s_token: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        min_score: float | None = None,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> str:
        """Асинхронно решает reCAPTCHA Enterprise.

        Args:
            config: Конфигурация задачи ReCaptchaEnterpriseConfig.
            site_key: Sitekey reCAPTCHA Enterprise.
            page_url: URL страницы.
            action: Действие (action).
            enterprise_payload: Полезная нагрузка Enterprise.
            s_token: Защитный токен s_token.
            user_agent: User-Agent.
            proxy: Прокси для решения.
            min_score: Минимальный требуемый score.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса (в секундах).

        Returns:
            Токен решения g-recaptcha-response.
        """
        return await self._sync_solver.asolve(
            config=config,
            site_key=site_key,
            page_url=page_url,
            action=action,
            enterprise_payload=enterprise_payload,
            s_token=s_token,
            user_agent=user_agent,
            proxy=proxy,
            min_score=min_score,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    async def asolve(
        self,
        config: ReCaptchaEnterpriseConfig | None = None,
        *,
        site_key: str | None = None,
        page_url: str | None = None,
        action: str | None = None,
        enterprise_payload: dict[str, str | int | float | bool] | None = None,
        s_token: str | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        min_score: float | None = None,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> str:
        """Алиас для solve.

        Args:
            config: Конфигурация задачи ReCaptchaEnterpriseConfig.
            site_key: Sitekey reCAPTCHA Enterprise.
            page_url: URL страницы.
            action: Действие (action).
            enterprise_payload: Полезная нагрузка Enterprise.
            s_token: Защитный токен s_token.
            user_agent: User-Agent.
            proxy: Прокси для решения.
            min_score: Минимальный требуемый score.
            timeout: Максимальное время ожидания решения (в секундах).
            poll_interval: Интервал опроса статуса (в секундах).

        Returns:
            Токен решения g-recaptcha-response.
        """
        return await self.solve(
            config=config,
            site_key=site_key,
            page_url=page_url,
            action=action,
            enterprise_payload=enterprise_payload,
            s_token=s_token,
            user_agent=user_agent,
            proxy=proxy,
            min_score=min_score,
            timeout=timeout,
            poll_interval=poll_interval,
        )
