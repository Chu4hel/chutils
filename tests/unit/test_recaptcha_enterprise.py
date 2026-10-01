from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from chutils.captcha.exceptions import CaptchaTimeoutError
from chutils.captcha.models import ReCaptchaEnterpriseConfig
from chutils.captcha.recaptcha_enterprise import (
    AsyncReCaptchaEnterpriseSolver,
    ReCaptchaEnterpriseSolver,
)
from chutils.exceptions import ChutilsConfigurationError


def test_recaptcha_enterprise_solver_init_missing_key() -> None:
    """Проверяет ошибку инициализации без API-ключа."""
    with patch("chutils.secret_manager.SecretManager.get_secret", return_value=None):
        with pytest.raises(ChutilsConfigurationError):
            ReCaptchaEnterpriseSolver(api_key=None)


def test_recaptcha_enterprise_solver_rucaptcha_sync_success() -> None:
    """Тестирует успешное синхронное решение reCAPTCHA Enterprise через RuCaptcha."""
    solver = ReCaptchaEnterpriseSolver(api_key="mock_key", provider="rucaptcha")

    mock_client = MagicMock()
    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"status": 1, "request": "task_re_1"}

    mock_poll_pending = MagicMock()
    mock_poll_pending.json.return_value = {"status": 0, "request": "CAPCHA_NOT_READY"}

    mock_poll_ready = MagicMock()
    mock_poll_ready.json.return_value = {
        "status": 1,
        "request": "g_recaptcha_enterprise_token_xyz",
    }

    mock_client.post.return_value = mock_post_resp
    mock_client.get.side_effect = [mock_poll_pending, mock_poll_ready]

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value = mock_client
        with patch("time.sleep", return_value=None):
            token = solver.solve(
                site_key="6Lf_site_key",
                page_url="https://example.com/login",
                action="login",
                s_token="sec_token",
                enterprise_payload={"risk": 1},
                poll_interval=0.01,
            )

    assert token == "g_recaptcha_enterprise_token_xyz"


def test_recaptcha_enterprise_solver_capmonster_sync_success() -> None:
    """Тестирует успешное синхронное решение через CapMonster."""
    solver = ReCaptchaEnterpriseSolver(api_key="mock_cm_key", provider="capmonster")

    mock_client = MagicMock()
    mock_create_resp = MagicMock()
    mock_create_resp.json.return_value = {"errorId": 0, "taskId": 8888}

    mock_result_resp = MagicMock()
    mock_result_resp.json.return_value = {
        "errorId": 0,
        "status": "ready",
        "solution": {"gRecaptchaResponse": "cm_enterprise_token_123"},
    }

    mock_client.post.side_effect = [mock_create_resp, mock_result_resp]

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value = mock_client
        with patch("time.sleep", return_value=None):
            cfg = ReCaptchaEnterpriseConfig(
                site_key="6Lf_site_key",
                page_url="https://example.com",
                action="submit",
            )
            token = solver.solve(cfg, poll_interval=0.01)

    assert token == "cm_enterprise_token_123"


def test_recaptcha_enterprise_solver_timeout() -> None:
    """Тестирует обработку таймаута решения."""
    solver = ReCaptchaEnterpriseSolver(api_key="mock_key", provider="rucaptcha")
    mock_client = MagicMock()
    mock_client.post.return_value.json.return_value = {"status": 1, "request": "task_1"}
    mock_client.get.return_value.json.return_value = {
        "status": 0,
        "request": "CAPCHA_NOT_READY",
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value = mock_client
        with patch("time.time", side_effect=[10.0, 11.0, 15.0, 50.0]):
            with patch("time.sleep", return_value=None):
                with pytest.raises(CaptchaTimeoutError):
                    solver.solve(site_key="key", page_url="url", timeout=1.0)


@pytest.mark.asyncio
async def test_recaptcha_enterprise_solver_async() -> None:
    """Тестирует асинхронное решение reCAPTCHA Enterprise через asolve."""
    solver = ReCaptchaEnterpriseSolver(api_key="mock_key", provider="rucaptcha")

    mock_client = MagicMock()
    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"status": 1, "request": "async_task"}

    mock_poll_ready = MagicMock()
    mock_poll_ready.json.return_value = {
        "status": 1,
        "request": "async_enterprise_token_777",
    }

    async def mock_post(*args, **kwargs):
        return mock_post_resp

    async def mock_get(*args, **kwargs):
        return mock_poll_ready

    mock_client.post = mock_post
    mock_client.get = mock_get

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        with patch("asyncio.sleep", return_value=None):
            token = await solver.asolve(
                site_key="async_key",
                page_url="https://example.com",
                poll_interval=0.01,
            )

    assert token == "async_enterprise_token_777"


@pytest.mark.asyncio
async def test_async_recaptcha_enterprise_solver_class() -> None:
    """Тестирует выделенный класс AsyncReCaptchaEnterpriseSolver."""
    async_solver = AsyncReCaptchaEnterpriseSolver(api_key="mock_key", provider="rucaptcha")
    with patch.object(
        async_solver._sync_solver,
        "asolve",
        return_value="mock_recaptcha_token",
    ):
        res = await async_solver.solve(site_key="key", page_url="url")
        assert res == "mock_recaptcha_token"
        res_alias = await async_solver.asolve(site_key="key", page_url="url")
        assert res_alias == "mock_recaptcha_token"
