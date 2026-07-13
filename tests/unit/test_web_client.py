from unittest.mock import MagicMock

import httpx
import pytest
from pytest_mock import MockerFixture

from chutils.exceptions import RateLimitExceededError
from chutils.web.client import WebClient
from chutils.web.proxy_pool import ProxyPool
from chutils.web.user_agent import UserAgentRotator


def test_web_client_user_agent_rotation(mocker: MockerFixture) -> None:
    """Проверяет ротацию User-Agent в WebClient."""
    mock_send = mocker.patch("httpx.Client.send")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.return_value = mock_response

    rotator = UserAgentRotator(user_agents=["TestUA-1", "TestUA-2"])
    client = WebClient(user_agent_rotator=rotator, rotate_ua=True)

    client.get("http://sync-ua.example.com")
    req1 = mock_send.call_args[0][0]
    assert req1.headers["user-agent"] in ["TestUA-1", "TestUA-2"]


def test_web_client_proxy_rotation_on_retry(mocker: MockerFixture) -> None:
    """Проверяет автосмену прокси при ошибках/повторах."""
    mock_send = mocker.patch("httpx.Client.send")
    mock_send.side_effect = [
        httpx.RequestError("Conn failed"),
        MagicMock(status_code=200),
    ]

    pool = ProxyPool(proxies=["http://proxy1:8080", "http://proxy2:8080"], strategy="round_robin")
    client = WebClient(proxy_pool=pool, rotate_proxy=True, retries=1, retry_delay=0.01)

    resp = client.get("http://sync-retry.example.com")
    assert resp.status_code == 200
    # Проверяем, что send был вызван 2 раза
    assert mock_send.call_count == 2


def test_web_client_rate_limit(mocker: MockerFixture) -> None:
    """Проверяет работу лимитера запросов в WebClient."""
    mock_send = mocker.patch("httpx.Client.send")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_send.return_value = mock_response

    # Настраиваем лимит 1 запрос в 10 секунд без ожидания
    client = WebClient(rate_limit_calls=1, rate_limit_period=10.0, rate_limit_wait=False)

    # Первый запрос должен пройти успешно
    client.get("http://sync-limit.example.com")

    # Второй запрос к тому же хосту должен выбросить RateLimitExceededError
    with pytest.raises(RateLimitExceededError):
        client.get("http://sync-limit.example.com")


def test_web_client_caching(mocker: MockerFixture) -> None:
    """Проверяет кэширование GET-запросов в WebClient."""
    mock_send = mocker.patch("httpx.Client.send")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.read.return_value = b"cached response"
    mock_send.return_value = mock_response

    client = WebClient(cache_ttl=5)

    # Первый запрос должен вызвать реальный send
    resp1 = client.get("http://sync-cache.example.com")
    assert resp1.read() == b"cached response"
    assert mock_send.call_count == 1

    # Второй запрос должен вернуть закэшированный ответ без вызова send
    resp2 = client.get("http://sync-cache.example.com")
    assert resp2.read() == b"cached response"
    assert mock_send.call_count == 1
