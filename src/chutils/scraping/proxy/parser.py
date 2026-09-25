"""Парсер строковых представлений и параметров прокси."""

from collections.abc import Mapping
from typing import Literal
from urllib.parse import unquote, urlsplit

from chutils.scraping.proxy.models import ProxyConfig

ProxyProtocol = Literal["http", "https", "socks5", "socks4", "socks5h", "socks4a"]


def parse_proxy(
    proxy: str | ProxyConfig | Mapping[str, object],
    default_protocol: ProxyProtocol = "http",
) -> ProxyConfig:
    """Парсит строку, словарь или существующий объект в экземпляр ProxyConfig.

    Поддерживает распространенные форматы:
    - URL: `http://user:pass@host:port`, `socks5://host:port`
    - Без схемы с @: `user:pass@host:port`
    - Колоночные: `host:port`, `host:port:user:pass`, `user:pass:host:port`

    Args:
        proxy: Строка прокси, словарь параметров или экземпляр ProxyConfig.
        default_protocol: Протокол по умолчанию, если схема не указана.

    Returns:
        Экземпляр ProxyConfig с валидированными полями.

    Raises:
        TypeError: Если передан неподдерживаемый тип данных.
        ValueError: Если строку прокси не удалось распознать или порт некорректен.
    """
    if isinstance(proxy, ProxyConfig):
        return proxy.model_copy()

    if isinstance(proxy, Mapping):
        return ProxyConfig.model_validate(proxy)

    if not isinstance(proxy, str):
        raise TypeError(
            f"Недопустимый тип для прокси: {type(proxy).__name__}, ожидается str, dict или ProxyConfig"
        )

    clean_str = proxy.strip().strip("'\"")
    if not clean_str:
        raise ValueError("Не удалось распознать формат прокси: пустая строка")

    protocol: str = default_protocol
    host: str = ""
    port: int = 0
    username: str | None = None
    password: str | None = None

    if "://" in clean_str:
        parsed = urlsplit(clean_str)
        if not parsed.scheme or not parsed.hostname or parsed.port is None:
            raise ValueError(
                f"Не удалось распознать формат прокси в URL схеме: {clean_str}"
            )
        protocol = parsed.scheme.lower()
        host = parsed.hostname
        port = parsed.port
        if parsed.username is not None:
            username = unquote(parsed.username)
        if parsed.password is not None:
            password = unquote(parsed.password)
    elif "@" in clean_str:
        auth_part, host_part = clean_str.split("@", 1)
        if ":" in auth_part:
            u_part, p_part = auth_part.split(":", 1)
            username = unquote(u_part)
            password = unquote(p_part)
        else:
            username = unquote(auth_part)

        if ":" not in host_part:
            raise ValueError(f"Отсутствует порт в прокси: {clean_str}")
        h_part, port_str = host_part.rsplit(":", 1)
        host = h_part.strip("[]")
        try:
            port = int(port_str)
        except ValueError as err:
            raise ValueError(f"Некорректный порт в прокси: {port_str}") from err
    else:
        parts = clean_str.split(":")
        if len(parts) == 2:
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError as err:
                raise ValueError(f"Некорректный порт: {parts[1]}") from err
        elif len(parts) == 4:
            if parts[1].isdigit():
                # host:port:user:pass
                host = parts[0]
                port = int(parts[1])
                username = parts[2]
                password = parts[3]
            elif parts[3].isdigit():
                # user:pass:host:port
                username = parts[0]
                password = parts[1]
                host = parts[2]
                port = int(parts[3])
            else:
                raise ValueError(f"Не удалось распознать формат прокси: {clean_str}")
        elif len(parts) == 3 and parts[1].isdigit():
            # host:port:user
            host = parts[0]
            port = int(parts[1])
            username = parts[2]
        else:
            raise ValueError(f"Не удалось распознать формат прокси: {clean_str}")

    if password:
        try:
            from chutils.logger.masking import _GLOBAL_MASKS, _update_mask_re

            if password not in _GLOBAL_MASKS:
                _GLOBAL_MASKS.add(password)
                _update_mask_re()
        except Exception:
            pass

    return ProxyConfig(
        protocol=protocol,  # type: ignore[arg-type]
        host=host,
        port=port,
        username=username,
        password=password,
    )

