from unittest.mock import MagicMock

import httpx
import pytest
from pytest_mock import MockerFixture

from chutils.exceptions import RateLimitExceededError
from chutils.web.client import AsyncWebClient
from chutils.web.proxy_pool import ProxyPool
from chutils.web.user_agent import UserAgentRotator


@pytest.mark.asyncio
async def test_async_web_client_user_agent_rotation(mocker: MockerFixture) -> None:
    """Проверяет ротацию User-Agent в AsyncWebClient."""
    mock_send = mocker.patch("httpx.AsyncClient.send")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.return_value = mock_response

    rotator = UserAgentRotator(user_agents=["TestUA-1", "TestUA-2"])
    client = AsyncWebClient(user_agent_rotator=rotator, rotate_ua=True)

    await client.get("http://async-ua.example.com")
    req1 = mock_send.call_args[0][0]
    assert req1.headers["user-agent"] in ["TestUA-1", "TestUA-2"]


@pytest.mark.asyncio
async def test_async_web_client_proxy_rotation_on_retry(mocker: MockerFixture) -> None:
    """Проверяет автосмену прокси при ошибках/повторах в асинхронном клиенте."""
    mock_send = mocker.patch("httpx.AsyncClient.send")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.side_effect = [
        httpx.RequestError("Conn failed"),
        mock_response,
    ]

    pool = ProxyPool(proxies=["http://proxy1:8080", "http://proxy2:8080"], strategy="round_robin")
    client = AsyncWebClient(proxy_pool=pool, rotate_proxy=True, retries=1, retry_delay=0.01)

    resp = await client.get("http://async-retry.example.com")
    assert resp.status_code == 200
    assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_async_web_client_rate_limit(mocker: MockerFixture) -> None:
    """Проверяет лимитер частоты запросов в AsyncWebClient."""
    mock_send = mocker.patch("httpx.AsyncClient.send")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.return_value = mock_response

    client = AsyncWebClient(rate_limit_calls=1, rate_limit_period=10.0, rate_limit_wait=False)

    await client.get("http://async-limit.example.com")

    with pytest.raises(RateLimitExceededError):
        await client.get("http://async-limit.example.com")


@pytest.mark.asyncio
async def test_async_web_client_caching(mocker: MockerFixture) -> None:
    """Проверяет кэширование GET-запросов в AsyncWebClient."""
    mock_send = mocker.patch("httpx.AsyncClient.send")
    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_aread() -> bytes:
        return b"cached response"

    mock_response.aread = mock_aread
    mock_response.read.return_value = b"cached response"
    mock_send.return_value = mock_response

    client = AsyncWebClient(cache_ttl=5)

    resp1 = await client.get("http://async-cache.example.com")
    assert resp1.read() == b"cached response"
    assert mock_send.call_count == 1

    resp2 = await client.get("http://async-cache.example.com")
    assert resp2.read() == b"cached response"
    assert mock_send.call_count == 1
