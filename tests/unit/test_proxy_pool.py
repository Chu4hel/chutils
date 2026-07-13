import time
from unittest.mock import MagicMock, patch

from chutils.web.proxy_pool import ProxyPool


def test_proxy_pool_static_list() -> None:
    """Проверяет инициализацию ProxyPool статическим списком прокси."""
    proxies = ["http://proxy1.com:8080", "http://proxy2.com:8080"]
    pool = ProxyPool(proxies=proxies, strategy="round_robin")
    assert len(pool.get_all_proxies()) == 2
    assert pool.get_next_proxy() == "http://proxy1.com:8080"
    assert pool.get_next_proxy() == "http://proxy2.com:8080"
    assert pool.get_next_proxy() == "http://proxy1.com:8080"


def test_proxy_pool_random_strategy() -> None:
    """Проверяет случайную стратегию выбора прокси."""
    proxies = ["http://proxy1.com:8080", "http://proxy2.com:8080"]
    pool = ProxyPool(proxies=proxies, strategy="random")
    p = pool.get_next_proxy()
    assert p in proxies


def test_proxy_pool_empty() -> None:
    """Проверяет поведение ProxyPool при отсутствии прокси."""
    pool = ProxyPool()
    assert pool.get_next_proxy() is None


@patch("urllib.request.getproxies")
def test_proxy_pool_env_proxies(mock_getproxies: MagicMock) -> None:
    """Проверяет загрузку прокси из переменных окружения."""
    mock_getproxies.return_value = {
        "http": "http://env-http-proxy:8080",
        "https": "http://env-https-proxy:8080",
    }
    pool = ProxyPool(use_env=True)
    all_proxies = pool.get_all_proxies()
    assert "http://env-http-proxy:8080" in all_proxies
    assert "http://env-https-proxy:8080" in all_proxies


@patch("urllib.request.urlopen")
def test_proxy_pool_url_load(mock_urlopen: MagicMock) -> None:
    """Проверяет загрузку списка прокси по URL."""
    mock_response = MagicMock()
    mock_response.read.return_value = b"http://proxy-url-1:8080\nhttp://proxy-url-2:8080\n# comment\n"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    pool = ProxyPool(url="http://example.com/proxies.txt")
    pool.update_from_url()

    all_proxies = pool.get_all_proxies()
    assert "http://proxy-url-1:8080" in all_proxies
    assert "http://proxy-url-2:8080" in all_proxies
    assert len(all_proxies) == 2


@patch("urllib.request.urlopen")
def test_proxy_pool_background_update(mock_urlopen: MagicMock) -> None:
    """Проверяет периодическое фоновое обновление списка прокси по URL."""
    # Возвращаем разные прокси при первом и втором вызове
    mock_response_1 = MagicMock()
    mock_response_1.read.return_value = b"http://proxy-bg-1:8080"
    mock_response_2 = MagicMock()
    mock_response_2.read.return_value = b"http://proxy-bg-2:8080"

    mock_urlopen.side_effect = [
        MagicMock(__enter__=MagicMock(return_value=mock_response_1)),
        MagicMock(__enter__=MagicMock(return_value=mock_response_2)),
    ]

    pool = ProxyPool(url="http://example.com/proxies.txt", update_interval=0.1)
    pool.start_background_update()
    try:
        # Даем отработать первому обновлению (происходит сразу)
        time.sleep(0.05)
        assert "http://proxy-bg-1:8080" in pool.get_all_proxies()

        # Ждем следующего интервала обновления
        time.sleep(0.12)
        assert "http://proxy-bg-2:8080" in pool.get_all_proxies()
    finally:
        pool.stop_background_update()
