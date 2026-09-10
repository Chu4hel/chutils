"""Модели данных конфигурации прокси-серверов."""

import base64
from typing import Literal

from pydantic import BaseModel, Field


class ProxyConfig(BaseModel):
    """Конфигурация прокси-сервера с поддержкой аутентификации."""

    protocol: Literal["http", "https", "socks5", "socks4", "socks5h", "socks4a"] = (
        "http"
    )
    host: str
    port: int = Field(ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def has_auth(self) -> bool:
        """Проверяет наличие учетных данных аутентификации."""
        return bool(self.username is not None and self.password is not None)

    @property
    def auth_str(self) -> str | None:
        """Возвращает строку аутентификации user:password или None."""
        if self.username is not None and self.password is not None:
            return f"{self.username}:{self.password}"
        return None

    @property
    def server_url(self) -> str:
        """Возвращает базовый URL прокси-сервера без учетных данных."""
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def url(self) -> str:
        """Возвращает полный URL прокси с учетными данными, если они есть."""
        if self.has_auth:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return self.server_url

    @property
    def masked_url(self) -> str:
        """Возвращает безопасный URL для логирования со скрытым паролем."""
        if self.has_auth:
            return f"{self.protocol}://{self.username}:***@{self.host}:{self.port}"
        return self.server_url

    @property
    def basic_auth_header(self) -> str | None:
        """Возвращает значение заголовка Proxy-Authorization Basic или None."""
        if not self.has_auth or self.username is None or self.password is None:
            return None
        creds = f"{self.username}:{self.password}".encode("utf-8")
        return f"Basic {base64.b64encode(creds).decode('utf-8')}"

    def to_playwright(self) -> dict[str, str]:
        """Преобразует конфигурацию в словарь параметров прокси для Playwright.

        Returns:
            Словарь с ключами server, username и password для playwright.
        """
        cfg: dict[str, str] = {"server": self.server_url}
        if self.username is not None:
            cfg["username"] = self.username
        if self.password is not None:
            cfg["password"] = self.password
        return cfg

    def to_chrome_arg(self) -> str:
        """Возвращает CLI аргумент --proxy-server для Chromium.

        Returns:
            Строка флага командной строки для запуска Chromium.
        """
        return f"--proxy-server={self.server_url}"

    def to_selenium(self) -> dict[str, str]:
        """Преобразует конфигурацию в словарь capabilities прокси для Selenium.

        Returns:
            Словарь параметров прокси для передачи в Selenium Capabilities.
        """
        host_port = f"{self.host}:{self.port}"
        return {
            "proxyType": "MANUAL",
            "httpProxy": host_port,
            "sslProxy": host_port,
        }

    def to_string(self, format: str = "url") -> str:
        """Форматирует прокси в строковое представление по заданному шаблону.

        Args:
            format: Шаблон формата ('url', 'host:port', 'host:port:user:pass', 'server').

        Returns:
            Строковое представление прокси.
        """
        match format:
            case "url":
                return self.url
            case "host:port":
                return f"{self.host}:{self.port}"
            case "host:port:user:pass":
                u = self.username or ""
                p = self.password or ""
                return f"{self.host}:{self.port}:{u}:{p}"
            case "server":
                return self.server_url
            case _:
                return self.url
