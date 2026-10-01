from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from chutils.captcha.exceptions import (
    CaptchaBalanceError,
    CaptchaTimeoutError,
)
from chutils.captcha.geetest import AsyncGeeTestSolver, GeeTestSolver
from chutils.captcha.models import GeeTestResult, GeeTestTaskConfig
from chutils.exceptions import ChutilsConfigurationError


def test_geetest_solver_init_missing_key() -> None:
    """Проверяет ошибку при отсутствии API-ключа."""
    with patch("chutils.secret_manager.SecretManager.get_secret", return_value=None):
        with pytest.raises(ChutilsConfigurationError):
            GeeTestSolver(api_key=None)


def test_geetest_solver_rucaptcha_sync_success() -> None:
    """Тестирует успешное синхронное решение GeeTest через RuCaptcha."""
    solver = GeeTestSolver(api_key="mock_key", provider="rucaptcha")

    mock_client = MagicMock()
    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"status": 1, "request": "task_12345"}

    mock_poll_pending = MagicMock()
    mock_poll_pending.json.return_value = {"status": 0, "request": "CAPCHA_NOT_READY"}

    solution_data = {
        "lot_number": "lot_mock_1",
        "pass_token": "pass_mock_1",
        "gen_time": "1726000001",
        "captcha_output": "sig_mock_1",
    }
    mock_poll_ready = MagicMock()
    mock_poll_ready.json.return_value = {
        "status": 1,
        "request": json.dumps(solution_data),
    }

    mock_client.post.return_value = mock_post_resp
    mock_client.get.side_effect = [mock_poll_pending, mock_poll_ready]

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value = mock_client
        with patch("time.sleep", return_value=None):
            result = solver.solve(
                captcha_id="geetest_id_123",
                page_url="https://example.com/login",
                poll_interval=0.01,
            )

    assert isinstance(result, GeeTestResult)
    assert result.lot_number == "lot_mock_1"
    assert result.pass_token == "pass_mock_1"
    assert result.gen_time == "1726000001"
    assert result.captcha_output == "sig_mock_1"
    assert result.captcha_id == "geetest_id_123"


def test_geetest_solver_rucaptcha_balance_error() -> None:
    """Тестирует обработку нулевого баланса RuCaptcha."""
    solver = GeeTestSolver(api_key="mock_key", provider="rucaptcha")
    mock_client = MagicMock()
    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"status": 0, "request": "ERROR_ZERO_BALANCE"}
    mock_client.post.return_value = mock_post_resp

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value = mock_client
        with pytest.raises(CaptchaBalanceError):
            solver.solve(captcha_id="id", page_url="https://example.com")


def test_geetest_solver_capmonster_sync_success() -> None:
    """Тестирует успешное синхронное решение через CapMonster."""
    solver = GeeTestSolver(api_key="mock_cm_key", provider="capmonster")

    mock_client = MagicMock()
    mock_create_resp = MagicMock()
    mock_create_resp.json.return_value = {"errorId": 0, "taskId": 9999}

    mock_result_resp = MagicMock()
    mock_result_resp.json.return_value = {
        "errorId": 0,
        "status": "ready",
        "solution": {
            "lot_number": "cm_lot",
            "pass_token": "cm_pass",
            "gen_time": "123456",
            "captcha_output": "cm_sig",
        },
    }

    mock_client.post.side_effect = [mock_create_resp, mock_result_resp]

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value = mock_client
        with patch("time.sleep", return_value=None):
            result = solver.solve(
                GeeTestTaskConfig(
                    captcha_id="cm_gt_id",
                    page_url="https://capmonster.com",
                    risk_type="slide",
                ),
                poll_interval=0.01,
            )

    assert result.lot_number == "cm_lot"
    assert result.pass_token == "cm_pass"
    assert result.captcha_id == "cm_gt_id"


def test_geetest_solver_timeout_error() -> None:
    """Тестирует превышение таймаута ожидания капчи."""
    solver = GeeTestSolver(api_key="mock_key", provider="rucaptcha")
    mock_client = MagicMock()
    mock_client.post.return_value.json.return_value = {"status": 1, "request": "task_1"}
    mock_client.get.return_value.json.return_value = {
        "status": 0,
        "request": "CAPCHA_NOT_READY",
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value = mock_client
        with patch("time.time", side_effect=[100.0, 101.0, 105.0, 200.0]):
            with patch("time.sleep", return_value=None):
                with pytest.raises(CaptchaTimeoutError):
                    solver.solve(captcha_id="id", page_url="url", timeout=2.0)


@pytest.mark.asyncio
async def test_geetest_solver_async_asolve() -> None:
    """Тестирует асинхронное решение GeeTest через asolve."""
    solver = GeeTestSolver(api_key="mock_key", provider="rucaptcha")

    mock_client = MagicMock()
    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"status": 1, "request": "async_task"}

    solution_data = {
        "lot_number": "async_lot",
        "pass_token": "async_pass",
        "gen_time": "123",
        "captcha_output": "async_sig",
    }
    mock_poll_ready = MagicMock()
    mock_poll_ready.json.return_value = {
        "status": 1,
        "request": solution_data,  # может вернуть сразу словарь
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
            res = await solver.asolve(
                captcha_id="async_gt",
                page_url="https://example.com/async",
                poll_interval=0.01,
            )

    assert res.lot_number == "async_lot"
    assert res.captcha_output == "async_sig"


@pytest.mark.asyncio
async def test_async_geetest_solver_class() -> None:
    """Тестирует выделенный класс AsyncGeeTestSolver."""
    async_solver = AsyncGeeTestSolver(api_key="mock_key", provider="rucaptcha")
    with patch.object(
        async_solver._sync_solver,
        "asolve",
        return_value=GeeTestResult(
            lot_number="l", pass_token="p", gen_time="g", captcha_output="o"
        ),
    ):
        res = await async_solver.solve(captcha_id="id", page_url="url")
        assert res.lot_number == "l"
        res_alias = await async_solver.asolve(captcha_id="id", page_url="url")
        assert res_alias.lot_number == "l"
