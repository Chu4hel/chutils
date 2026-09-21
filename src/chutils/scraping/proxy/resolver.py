"""
Модуль умного разрешения форматов прокси, проверки доступности и дискового кэширования.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
import time
from urllib.parse import quote, unquote, urlsplit

from pydantic import BaseModel, Field

from chutils import setup_logger
from chutils.scraping.proxy.cache import FileCacheBackend
from chutils.scraping.proxy.models import ProxyConfig, ProxyHealthResult
from chutils.scraping.proxy.parser import parse_proxy

logger = setup_logger(__name__)

__all__ = ["FileCacheBackend", "ProxyCandidate", "SmartProxyResolver"]


class ProxyCandidate(BaseModel):
    """Модель кандидата прокси с нормализованными компонентами."""

    protocol: str = Field(default="http", description="Протокол прокси (http, socks5 и др.)")
    host: str = Field(..., description="Хост или IP-адрес")
    port: int = Field(..., ge=1, le=65535, description="Порт прокси")
    username: str | None = Field(default=None, description="Имя пользователя для авторизации")
    password: str | None = Field(default=None, description="Пароль для авторизации")

    @property
    def url(self) -> str:
        """Возвращает нормализованный URL прокси."""
        if self.username and self.password is not None:
            u_enc = quote(self.username, safe="")
            p_enc = quote(self.password, safe="")
            return f"{self.protocol}://{u_enc}:{p_enc}@{self.host}:{self.port}"
        if self.username:
            u_enc = quote(self.username, safe="")
            return f"{self.protocol}://{u_enc}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"

    def to_proxy_config(self) -> ProxyConfig:
        """Преобразует кандидата в экземпляр ProxyConfig.

        Returns:
            Сконфигурированный объект ProxyConfig.
        """
        return ProxyConfig(
            protocol=self.protocol,  # type: ignore[arg-type]
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        )


class SmartProxyResolver:
    """Умный резолвер и верификатор форматов прокси с активным зондированием и дисковым кэшированием."""

    def __init__(
        self,
        cache_path: Path | str | None = None,
        probe_timeout: float = 2.5,
        target_url: str = "http://www.google.com/generate_204",
    ) -> None:
        """Инициализирует резолвер прокси.

        Args:
            cache_path: Путь к файлу кэша. Если не указан, используется .chutils/proxy_cache.json.
            probe_timeout: Таймаут проверки соединения с кандидатом в секундах.
            target_url: Целевой легковесный URL для тестового HTTP GET-запроса при проверке.
        """
        p = Path(cache_path or ".chutils/proxy_cache.json")
        self.cache = FileCacheBackend(p)
        self.probe_timeout = probe_timeout
        self.target_url = target_url

    def generate_candidates(self, raw_proxy: str | None) -> list[str]:
        """Генерирует список кандидатов URL прокси в порядке приоритета проверки.

        Поддерживает форматы:
        - `host:port:user:pass` (приоритет: http, затем socks5)
        - `user:pass:host:port`
        - `user:pass@host:port`
        - `host:port@user:pass`
        - `host:port`
        - `http://...`, `socks5://...` (выбранный протокол, затем альтернатива)

        Args:
            raw_proxy: Исходная строка прокси.

        Returns:
            Список нормализованных URL-адресов кандидатов.
        """
        if not raw_proxy:
            return []
        clean = raw_proxy.strip().strip("'\"")
        if not clean:
            return []

        scheme_prefix: str | None = None
        core = clean
        if "://" in clean:
            scheme_prefix, core = clean.split("://", 1)
            scheme_prefix = scheme_prefix.lower()

        # Определение очередности протоколов
        if scheme_prefix in ("socks5", "socks5h"):
            protocols = ["socks5", "http"]
        elif scheme_prefix in ("http", "https"):
            protocols = ["http", "socks5"]
        elif scheme_prefix in ("socks4", "socks4a"):
            protocols = ["socks4", "socks5", "http"]
        else:
            protocols = ["http", "socks5"]

        candidates: list[str] = []

        def _add_candidate(proto: str, host: str, port: int, user: str | None, pwd: str | None) -> None:
            if not host or port <= 0 or port > 65535:
                return
            clean_host = host.strip("[]")
            cand = ProxyCandidate(
                protocol=proto,
                host=clean_host,
                port=port,
                username=unquote(user) if user else None,
                password=unquote(pwd) if pwd is not None else None,
            )
            url = cand.url
            if url not in candidates:
                candidates.append(url)

        # 1. Формат с @: user:pass@host:port или host:port@user:pass
        if "@" in core:
            p1, p2 = core.split("@", 1)
            p1_has_port = ":" in p1 and p1.rsplit(":", 1)[1].isdigit()
            p2_has_port = ":" in p2 and p2.rsplit(":", 1)[1].isdigit()

            if p2_has_port:
                auth_part, host_part = p1, p2
            elif p1_has_port:
                host_part, auth_part = p1, p2
            else:
                auth_part, host_part = p1, p2

            h_str, port_val = "", 0
            if ":" in host_part:
                h_str, port_str = host_part.rsplit(":", 1)
                port_val = int(port_str) if port_str.isdigit() else 0

            u_str, pwd_str = None, None
            if ":" in auth_part:
                u_str, pwd_str = auth_part.split(":", 1)
            else:
                u_str = auth_part

            for proto in protocols:
                _add_candidate(proto, h_str, port_val, u_str, pwd_str)

        else:
            parts = core.split(":")
            if len(parts) == 4:
                p0, p1, p2, p3 = parts
                p1_is_num = p1.isdigit()
                p3_is_num = p3.isdigit()

                if p1_is_num:
                    # По умолчанию: host:port:user:pass -> http, затем socks5
                    for proto in protocols:
                        _add_candidate(proto, p0, int(p1), p2, p3)

                if p3_is_num:
                    # Формат: user:pass:host:port -> http, затем socks5
                    for proto in protocols:
                        _add_candidate(proto, p2, int(p3), p0, p1)

                if not p1_is_num and not p3_is_num:
                    try:
                        for proto in protocols:
                            _add_candidate(proto, p0, int(p1), p2, p3)
                    except ValueError:
                        pass

            elif len(parts) == 2:
                h_str, port_str = parts
                if port_str.isdigit():
                    for proto in protocols:
                        _add_candidate(proto, h_str, int(port_str), None, None)

            elif len(parts) == 3:
                p0, p1, p2 = parts
                if p1.isdigit():
                    for proto in protocols:
                        _add_candidate(proto, p0, int(p1), p2, None)
                elif p2.isdigit():
                    for proto in protocols:
                        _add_candidate(proto, p0, int(p2), p1, None)

        return candidates

    async def probe_proxy(self, candidate_url: str) -> bool:
        """Проверяет реальную сетевую доступность и валидность авторизации кандидата прокси.

        Args:
            candidate_url: URL кандидата прокси.

        Returns:
            True, если прокси успешно ответил на рукопожатие или запрос, иначе False.
        """
        parsed = urlsplit(candidate_url)
        scheme = (parsed.scheme or "http").lower()
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            return False

        user = unquote(parsed.username) if parsed.username else None
        pwd = unquote(parsed.password) if parsed.password else None

        if scheme in ("http", "https"):
            return await self._probe_http(host, port, user, pwd, self.probe_timeout)
        if scheme in ("socks5", "socks5h"):
            return await self._probe_socks5(host, port, user, pwd, self.probe_timeout)
        if scheme in ("socks4", "socks4a"):
            return await self._probe_socks4(host, port, user, self.probe_timeout)

        return False

    async def check_health(self, candidate_url: str) -> ProxyHealthResult:
        """Выполняет комплексный Health Check прокси с замером задержки (latency).

        Args:
            candidate_url: URL кандидата прокси для проверки.

        Returns:
            Экземпляр ProxyHealthResult со статусом доступности и задержкой в мс.
        """
        start = time.perf_counter()
        try:
            ok = await self.probe_proxy(candidate_url)
            latency = (time.perf_counter() - start) * 1000.0
            if ok:
                return ProxyHealthResult(is_alive=True, latency_ms=round(latency, 2))
            return ProxyHealthResult(
                is_alive=False,
                latency_ms=round(latency, 2),
                error="Handshake or connection probe failed",
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000.0
            return ProxyHealthResult(
                is_alive=False,
                latency_ms=round(latency, 2),
                error=str(exc),
            )

    async def _probe_http(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        timeout: float,
    ) -> bool:
        """Проверяет HTTP прокси через HTTP CONNECT или GET-запрос к легковесному эндпоинту."""
        writer = None
        try:
            connect_coro = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)

            headers = [
                b"CONNECT www.google.com:443 HTTP/1.1",
                b"Host: www.google.com:443",
                b"Proxy-Connection: Keep-Alive",
                b"User-Agent: chutils-proxy-probe/1.0",
            ]
            if username and password is not None:
                creds = f"{username}:{password}".encode("utf-8")
                b64 = base64.b64encode(creds).decode("ascii")
                headers.append(f"Proxy-Authorization: Basic {b64}".encode("ascii"))

            req = b"\r\n".join(headers) + b"\r\n\r\n"
            writer.write(req)
            await writer.drain()

            resp_line = await asyncio.wait_for(reader.readline(), timeout=timeout)
            if not resp_line:
                return False

            line_str = resp_line.decode("utf-8", errors="ignore")
            if " 200 " in line_str or line_str.startswith("HTTP/1.1 200") or line_str.startswith("HTTP/1.0 200"):
                return True

            if " 407 " in line_str:
                return False

            # Фолбэк для HTTP-прокси, не поддерживающих метод CONNECT
            if any(code in line_str for code in (" 405 ", " 403 ", " 501 ")):
                target_parsed = urlsplit(self.target_url)
                target_host = target_parsed.hostname or "www.google.com"
                get_headers = [
                    f"GET {self.target_url} HTTP/1.1".encode("ascii"),
                    f"Host: {target_host}".encode("ascii"),
                    b"Proxy-Connection: close",
                    b"User-Agent: chutils-proxy-probe/1.0",
                ]
                if username and password is not None:
                    creds = f"{username}:{password}".encode("utf-8")
                    b64 = base64.b64encode(creds).decode("ascii")
                    get_headers.append(f"Proxy-Authorization: Basic {b64}".encode("ascii"))
                writer.write(b"\r\n".join(get_headers) + b"\r\n\r\n")
                await writer.drain()
                get_resp = await asyncio.wait_for(reader.readline(), timeout=timeout)
                get_str = get_resp.decode("utf-8", errors="ignore")
                if any(ok_code in get_str for ok_code in (" 200 ", " 204 ", " 301 ", " 302 ")):
                    return True

            return False
        except Exception:
            return False
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def _probe_socks5(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        timeout: float,
    ) -> bool:
        """Проверяет SOCKS5 прокси через рукопожатие RFC 1928 / RFC 1929."""
        writer = None
        try:
            connect_coro = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)

            # 1. Отправляем приветствие: SOCKS v5, 2 метода (0x00 без пароля, 0x02 user/pass)
            writer.write(b"\x05\x02\x00\x02")
            await writer.drain()

            greeting = await asyncio.wait_for(reader.readexactly(2), timeout=timeout)
            if len(greeting) < 2 or greeting[0] != 5:
                return False

            auth_method = greeting[1]
            if auth_method == 0xFF:
                return False

            if auth_method == 0x02:
                if not username or password is None:
                    return False
                u_bytes = username.encode("utf-8")
                p_bytes = password.encode("utf-8")
                if len(u_bytes) > 255 or len(p_bytes) > 255:
                    return False
                auth_req = bytes([1, len(u_bytes)]) + u_bytes + bytes([len(p_bytes)]) + p_bytes
                writer.write(auth_req)
                await writer.drain()

                auth_resp = await asyncio.wait_for(reader.readexactly(2), timeout=timeout)
                if len(auth_resp) < 2 or auth_resp[1] != 0x00:
                    return False
            elif auth_method == 0x00:
                pass
            else:
                return False

            # 2. Попытка SOCKS5 CONNECT к www.google.com:443
            domain = b"www.google.com"
            connect_req = (
                b"\x05\x01\x00\x03"
                + bytes([len(domain)])
                + domain
                + (443).to_bytes(2, "big")
            )
            writer.write(connect_req)
            await writer.drain()

            conn_resp = await asyncio.wait_for(reader.read(16), timeout=timeout)
            if len(conn_resp) >= 2 and conn_resp[1] == 0x00:
                return True

            # Если рукопожатие успешно пройдено, считаем прокси доступным
            return len(conn_resp) >= 2
        except Exception:
            return False
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def _probe_socks4(
        self,
        host: str,
        port: int,
        username: str | None,
        timeout: float,
    ) -> bool:
        """Проверяет SOCKS4 прокси."""
        writer = None
        try:
            connect_coro = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)

            user_bytes = (username or "nobody").encode("utf-8")
            # SOCKS4 CONNECT к 1.1.1.1:80
            req = b"\x04\x01" + (80).to_bytes(2, "big") + bytes([1, 1, 1, 1]) + user_bytes + b"\x00"
            writer.write(req)
            await writer.drain()

            resp = await asyncio.wait_for(reader.read(8), timeout=timeout)
            if len(resp) >= 2 and resp[1] in (0x5A, 0x5B):
                return True
            return False
        except Exception:
            return False
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def resolve(
        self,
        raw_proxy: str | None,
        force_check: bool = False,
        default_fallback: bool = True,
        force: bool = False,
    ) -> str | None:
        """Определяет корректный формат, проверяет доступность кандидатов и возвращает рабочий URL.

        Args:
            raw_proxy: Исходная строка прокси от пользователя.
            force_check: Игнорировать дисковый кэш и принудительно провести сетевой опрос.
            default_fallback: Возвращать лучший нормализованный URL при недоступности всех кандидатов.
            force: Синоним force_check для обратной совместимости.

        Returns:
            Нормализованный валидный URL прокси или None при пустом вводе.
        """
        if not raw_proxy or not raw_proxy.strip():
            return None

        clean_raw = raw_proxy.strip().strip("'\"")
        should_force = force_check or force

        # 1. Проверяем дисковый кэш
        if not should_force:
            cached = self.cache.get(clean_raw)
            if cached:
                try:
                    masked_cached = parse_proxy(cached).masked_url
                except Exception:
                    masked_cached = "***"
                logger.debug("Прокси найден в кэше: %s", masked_cached)
                return cached

        # 2. Генерируем кандидатов
        candidates = self.generate_candidates(clean_raw)
        if not candidates:
            return clean_raw

        # 3. Последовательно опрашиваем кандидатов (HTTP -> SOCKS5 -> перестановки)
        for cand in candidates:
            try:
                masked_cand = parse_proxy(cand).masked_url
            except Exception:
                masked_cand = cand
            logger.debug("Проверка кандидата прокси: %s", masked_cand)
            if await self.probe_proxy(cand):
                logger.info("Кандидат прокси успешно верифицирован: %s", masked_cand)
                self.cache.set(clean_raw, cand, ttl=7 * 86400)
                return cand

        logger.warning(
            "Ни один кандидат прокси не прошел сетевую проверку. Протестировано: %d",
            len(candidates),
        )
        if default_fallback and candidates:
            return candidates[0]

        return clean_raw

    async def resolve_config(
        self,
        raw_proxy: str | None,
        force_check: bool = False,
        default_fallback: bool = True,
        force: bool = False,
    ) -> ProxyConfig | None:
        """Резолвит прокси и возвращает структурированный объект ProxyConfig.

        Args:
            raw_proxy: Исходная строка прокси.
            force_check: Принудительно выполнить сетевую проверку без кэша.
            default_fallback: Использовать первый валидный кандидат при недоступности сети.
            force: Синоним force_check для обратной совместимости.

        Returns:
            Экземпляр ProxyConfig или None при пустом вводе.
        """
        resolved_url = await self.resolve(
            raw_proxy,
            force_check=force_check,
            default_fallback=default_fallback,
            force=force,
        )
        if not resolved_url:
            return None
        return parse_proxy(resolved_url)

    def resolve_sync(
        self,
        raw_proxy: str | None,
        force_check: bool = False,
        default_fallback: bool = True,
        force: bool = False,
    ) -> str | None:
        """Синхронная обертка для асинхронного метода resolve.

        Args:
            raw_proxy: Исходная строка прокси.
            force_check: Принудительно выполнить опрос без учета кэша.
            default_fallback: Возвращать лучший кандидат при неудаче проверки.
            force: Синоним force_check для обратной совместимости.

        Returns:
            Рабочий URL прокси или None.
        """
        if not raw_proxy or not raw_proxy.strip():
            return None

        should_force = force_check or force

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                fut = executor.submit(
                    asyncio.run,
                    self.resolve(
                        raw_proxy,
                        force_check=should_force,
                        default_fallback=default_fallback,
                    ),
                )
                return fut.result()
        return asyncio.run(
            self.resolve(
                raw_proxy,
                force_check=should_force,
                default_fallback=default_fallback,
            )
        )

    def resolve_config_sync(
        self,
        raw_proxy: str | None,
        force_check: bool = False,
        default_fallback: bool = True,
        force: bool = False,
    ) -> ProxyConfig | None:
        """Синхронная обертка для асинхронного метода resolve_config.

        Args:
            raw_proxy: Исходная строка прокси.
            force_check: Принудительно выполнить опрос без учета кэша.
            default_fallback: Возвращать лучший кандидат при неудаче проверки.
            force: Синоним force_check для обратной совместимости.

        Returns:
            Экземпляр ProxyConfig или None.
        """
        resolved_url = self.resolve_sync(
            raw_proxy,
            force_check=force_check,
            default_fallback=default_fallback,
            force=force,
        )
        if not resolved_url:
            return None
        return parse_proxy(resolved_url)
