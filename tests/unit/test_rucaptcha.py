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
    client.get = AsyncMock()
    client_context.__aenter__.return_value = client
    with patch("httpx.AsyncClient", return_value=client_context):
        yield client


def test_rucaptcha_solve_image_success(mock_httpx_client) -> None:
    """Проверяет успешное решение текстовой капчи по картинке."""
    from chutils.scraping.captcha.rucaptcha import RuCaptchaSolver

    response_in = MagicMock()
    response_in.json.return_value = {"status": 1, "request": "12345"}

    response_res = MagicMock()
    response_res.json.return_value = {"status": 1, "request": "abcd"}

    mock_httpx_client.post.return_value = response_in
    mock_httpx_client.get.return_value = response_res

    solver = RuCaptchaSolver(api_key="test_key")
    result = solver.solve_image(image_data=b"dummy_bytes", poll_interval=0.001)

    assert result == "abcd"
    mock_httpx_client.post.assert_called_once()
    mock_httpx_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_async_rucaptcha_solve_recaptcha_success(mock_httpx_async_client) -> None:
    """Проверяет успешное асинхронное решение ReCaptcha."""
    from chutils.scraping.captcha.rucaptcha import AsyncRuCaptchaSolver

    response_in = MagicMock()
    response_in.json.return_value = {"status": 1, "request": "9999"}

    response_res = MagicMock()
    response_res.json.return_value = {"status": 1, "request": "recaptcha_token_xyz"}

    mock_httpx_async_client.post.return_value = response_in
    mock_httpx_async_client.get.return_value = response_res

    solver = AsyncRuCaptchaSolver(api_key="test_key")
    result = await solver.solve_recaptcha(
        sitekey="site_key_123", page_url="http://example.com", poll_interval=0.001
    )

    assert result == "recaptcha_token_xyz"
    mock_httpx_async_client.post.assert_called_once()
    mock_httpx_async_client.get.assert_called_once()


def test_rucaptcha_raises_balance_error(mock_httpx_client) -> None:
    """Проверяет выброс CaptchaBalanceError при нулевом балансе."""
    from chutils.scraping.captcha.rucaptcha import RuCaptchaSolver
    from chutils.scraping.captcha.exceptions import CaptchaBalanceError

    response_in = MagicMock()
    response_in.json.return_value = {"status": 0, "request": "ERROR_ZERO_BALANCE"}
    mock_httpx_client.post.return_value = response_in

    solver = RuCaptchaSolver(api_key="test_key")
    with pytest.raises(CaptchaBalanceError) as exc_info:
        solver.solve_image(image_data=b"dummy")

    assert "Баланс" in str(exc_info.value)


def test_rucaptcha_raises_service_error(mock_httpx_client) -> None:
    """Проверяет выброс CaptchaServiceError при неверном ключе."""
    from chutils.scraping.captcha.rucaptcha import RuCaptchaSolver
    from chutils.scraping.captcha.exceptions import CaptchaServiceError

    response_in = MagicMock()
    response_in.json.return_value = {"status": 0, "request": "ERROR_WRONG_USER_KEY"}
    mock_httpx_client.post.return_value = response_in

    solver = RuCaptchaSolver(api_key="test_key")
    with pytest.raises(CaptchaServiceError) as exc_info:
        solver.solve_image(image_data=b"dummy")

    assert "пользователя" in str(exc_info.value) or "пользователь" in str(exc_info.value) or "ключ" in str(
        exc_info.value)
