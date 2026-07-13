from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_httpx_installed(mocker) -> None:
    import importlib.util
    orig_find_spec = importlib.util.find_spec

    def custom_find_spec(name: str, package: str | None = None) -> Any:
        if name == "httpx":
            mock_spec = MagicMock()
            mock_spec.__spec__ = MagicMock()
            return mock_spec
        return orig_find_spec(name, package)

    mocker.patch("importlib.util.find_spec", side_effect=custom_find_spec)


@pytest.fixture
def mock_httpx_client():
    client_context = MagicMock()
    client = MagicMock()
    client_context.__enter__.return_value = client
    with patch("httpx.Client", return_value=client_context):
        yield client


@pytest.fixture
def mock_httpx_async_client():
    client_context = MagicMock()
    client = MagicMock()
    client.post = AsyncMock()
    client_context.__aenter__.return_value = client
    with patch("httpx.AsyncClient", return_value=client_context):
        yield client


def test_anticaptcha_solve_image_success(mock_httpx_client) -> None:
    """Проверяет успешное решение текстовой капчи по картинке."""
    from chutils.scraping.captcha.anticaptcha import AntiCaptchaSolver

    response_in = MagicMock()
    response_in.json.return_value = {"errorId": 0, "taskId": 12345}

    response_res = MagicMock()
    response_res.json.return_value = {
        "errorId": 0,
        "status": "ready",
        "solution": {"text": "abcd"}
    }

    mock_httpx_client.post.side_effect = [response_in, response_res]

    solver = AntiCaptchaSolver(api_key="test_key")
    result = solver.solve_image(image_data=b"dummy_bytes", poll_interval=0.001)

    assert result == "abcd"
    assert mock_httpx_client.post.call_count == 2


@pytest.mark.asyncio
async def test_async_anticaptcha_solve_recaptcha_success(mock_httpx_async_client) -> None:
    """Проверяет успешное асинхронное решение ReCaptcha."""
    from chutils.scraping.captcha.anticaptcha import AsyncAntiCaptchaSolver

    response_in = MagicMock()
    response_in.json.return_value = {"errorId": 0, "taskId": 9999}

    response_res = MagicMock()
    response_res.json.return_value = {
        "errorId": 0,
        "status": "ready",
        "solution": {"gRecaptchaResponse": "token_xyz"}
    }

    mock_httpx_async_client.post.side_effect = [response_in, response_res]

    solver = AsyncAntiCaptchaSolver(api_key="test_key")
    result = await solver.solve_recaptcha(
        sitekey="site_key_123", page_url="http://example.com", poll_interval=0.001
    )

    assert result == "token_xyz"
    assert mock_httpx_async_client.post.call_count == 2


def test_anticaptcha_raises_balance_error(mock_httpx_client) -> None:
    """Проверяет выброс CaptchaBalanceError при ошибке баланса."""
    from chutils.scraping.captcha.anticaptcha import AntiCaptchaSolver
    from chutils.scraping.captcha.exceptions import CaptchaBalanceError

    response_in = MagicMock()
    response_in.json.return_value = {
        "errorId": 10,
        "errorCode": "ERROR_ZERO_BALANCE",
        "errorDescription": "Zero balance"
    }
    mock_httpx_client.post.return_value = response_in

    solver = AntiCaptchaSolver(api_key="test_key")
    with pytest.raises(CaptchaBalanceError) as exc_info:
        solver.solve_image(image_data=b"dummy")

    assert "баланс" in str(exc_info.value).lower()


def test_anticaptcha_raises_service_error(mock_httpx_client) -> None:
    """Проверяет выброс CaptchaServiceError при ошибке ключа API."""
    from chutils.scraping.captcha.anticaptcha import AntiCaptchaSolver
    from chutils.scraping.captcha.exceptions import CaptchaServiceError

    response_in = MagicMock()
    response_in.json.return_value = {
        "errorId": 1,
        "errorCode": "ERROR_KEY_DOES_NOT_EXIST",
        "errorDescription": "Key does not exist"
    }
    mock_httpx_client.post.return_value = response_in

    solver = AntiCaptchaSolver(api_key="test_key")
    with pytest.raises(CaptchaServiceError) as exc_info:
        solver.solve_image(image_data=b"dummy")

    assert "ключ" in str(exc_info.value).lower() or "key" in str(exc_info.value).lower()
