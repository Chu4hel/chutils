"""Тесты для модели ProxyConfig и парсера прокси (chutils.scraping.proxy)."""

import pytest

from chutils.scraping.proxy.models import ProxyConfig
from chutils.scraping.proxy.parser import parse_proxy


def test_proxy_config_basic_properties() -> None:
    """Проверяет основные свойства модели ProxyConfig без аутентификации."""
    proxy = ProxyConfig(host="1.2.3.4", port=8080, protocol="http")
    assert proxy.host == "1.2.3.4"
    assert proxy.port == 8080
    assert proxy.protocol == "http"
    assert proxy.username is None
    assert proxy.password is None
    assert not proxy.has_auth
    assert proxy.auth_str is None
    assert proxy.server_url == "http://1.2.3.4:8080"
    assert proxy.url == "http://1.2.3.4:8080"
    assert proxy.masked_url == "http://1.2.3.4:8080"
    assert proxy.basic_auth_header is None
    assert proxy.to_chrome_arg() == "--proxy-server=http://1.2.3.4:8080"
    assert proxy.to_playwright() == {"server": "http://1.2.3.4:8080"}
    assert proxy.to_selenium() == {
        "proxyType": "MANUAL",
        "httpProxy": "1.2.3.4:8080",
        "sslProxy": "1.2.3.4:8080",
    }


def test_proxy_config_with_auth() -> None:
    """Проверяет свойства модели ProxyConfig с аутентификацией."""
    proxy = ProxyConfig(
        host="proxy.example.com",
        port=9090,
        protocol="socks5",
        username="user123",
        password="secret_password",
    )
    assert proxy.has_auth
    assert proxy.auth_str == "user123:secret_password"
    assert proxy.server_url == "socks5://proxy.example.com:9090"
    assert proxy.url == "socks5://user123:secret_password@proxy.example.com:9090"
    assert proxy.masked_url == "socks5://user123:***@proxy.example.com:9090"
    assert proxy.basic_auth_header is not None
    assert proxy.basic_auth_header.startswith("Basic ")
    # Проверяем Playwright формат с авторизацией
    pw_dict = proxy.to_playwright()
    assert pw_dict == {
        "server": "socks5://proxy.example.com:9090",
        "username": "user123",
        "password": "secret_password",
    }
    # Chrome CLI принимает только хост:порт без кредов
    assert proxy.to_chrome_arg() == "--proxy-server=socks5://proxy.example.com:9090"


def test_parse_proxy_standard_urls() -> None:
    """Проверяет парсинг стандартных URL форматов."""
    p1 = parse_proxy("http://192.168.1.1:8080")
    assert p1.protocol == "http"
    assert p1.host == "192.168.1.1"
    assert p1.port == 8080
    assert not p1.has_auth

    p2 = parse_proxy("https://admin:pass123@secure-proxy.org:8443")
    assert p2.protocol == "https"
    assert p2.host == "secure-proxy.org"
    assert p2.port == 8443
    assert p2.username == "admin"
    assert p2.password == "pass123"

    p3 = parse_proxy("socks5://user:pass@10.0.0.1:1080")
    assert p3.protocol == "socks5"
    assert p3.host == "10.0.0.1"
    assert p3.port == 1080
    assert p3.username == "user"
    assert p3.password == "pass"


def test_parse_proxy_colon_separated() -> None:
    """Проверяет парсинг форматов разделенных двоеточием."""
    # host:port
    p1 = parse_proxy("192.168.1.50:3128")
    assert p1.protocol == "http"
    assert p1.host == "192.168.1.50"
    assert p1.port == 3128
    assert not p1.has_auth

    # host:port:user:pass
    p2 = parse_proxy("192.168.1.50:3128:testuser:testpass")
    assert p2.protocol == "http"
    assert p2.host == "192.168.1.50"
    assert p2.port == 3128
    assert p2.username == "testuser"
    assert p2.password == "testpass"

    # user:pass:host:port
    p3 = parse_proxy("myuser:mypassword:proxy.net:8888")
    assert p3.protocol == "http"
    assert p3.host == "proxy.net"
    assert p3.port == 8888
    assert p3.username == "myuser"
    assert p3.password == "mypassword"

    # user:pass@host:port (без схемы)
    p4 = parse_proxy("user:pass@1.1.1.1:8000")
    assert p4.protocol == "http"
    assert p4.host == "1.1.1.1"
    assert p4.port == 8000
    assert p4.username == "user"
    assert p4.password == "pass"


def test_parse_proxy_from_dict_and_model() -> None:
    """Проверяет создание из словаря и копирование существующей модели."""
    d = {
        "protocol": "http",
        "host": "127.0.0.1",
        "port": 8080,
        "username": "u",
        "password": "p",
    }
    p1 = parse_proxy(d)
    assert p1.host == "127.0.0.1"
    assert p1.username == "u"

    p2 = parse_proxy(p1)
    assert p2 == p1
    assert p2 is not p1


def test_parse_proxy_invalid() -> None:
    """Проверяет обработку ошибок при невалидных входных данных."""
    with pytest.raises(ValueError, match="Не удалось распознать формат"):
        parse_proxy("")

    with pytest.raises(ValueError, match="Не удалось распознать формат"):
        parse_proxy("just-a-string")

    with pytest.raises(ValueError):
        parse_proxy("host:invalid_port")

    with pytest.raises(ValueError):
        parse_proxy("host:70000")

    with pytest.raises(TypeError):
        parse_proxy(12345)  # type: ignore[arg-type]


def test_proxy_config_to_string() -> None:
    """Проверяет форматирование ProxyConfig в различные строковые представления."""
    proxy = ProxyConfig(
        host="1.2.3.4", port=8080, protocol="http", username="u", password="p"
    )
    assert proxy.to_string("url") == "http://u:p@1.2.3.4:8080"
    assert proxy.to_string("host:port") == "1.2.3.4:8080"
    assert proxy.to_string("host:port:user:pass") == "1.2.3.4:8080:u:p"
    assert proxy.to_string("server") == "http://1.2.3.4:8080"
