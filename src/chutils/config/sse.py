"""
Модуль для работы с SSE (Server-Sent Events) клиентом.
Позволяет получать push-уведомления об изменениях конфигурации в реальном времени.
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
import threading
import urllib.request
from collections.abc import Callable, Iterable, Iterator

logger = logging.getLogger(__name__)


class SseEvent:
    """
    Представляет отдельное событие Server-Sent Events (SSE).

    Attributes:
        event: Тип события (по умолчанию 'message').
        data: Данные события.
        event_id: Идентификатор события (если передан).
        retry: Задержка повторного подключения в миллисекундах (если передано).
    """

    def __init__(
        self,
        event: str = "message",
        data: str = "",
        event_id: str | None = None,
        retry: int | None = None,
    ) -> None:
        self.event = event
        self.data = data
        self.event_id = event_id
        self.retry = retry

    def __repr__(self) -> str:
        return (
            f"SseEvent(event={self.event!r}, data={self.data!r}, "
            f"event_id={self.event_id!r}, retry={self.retry!r})"
        )


def parse_sse_lines(lines: Iterable[str]) -> Iterator[SseEvent]:
    """
    Генератор для парсинга строк SSE-потока в объекты SseEvent.

    Args:
        lines: Итерируемый объект со строками из SSE-потока.

    Yields:
        Объекты SseEvent по мере накопления данных.
    """
    current_event = "message"
    data_buffer: list[str] = []
    current_id: str | None = None
    current_retry: int | None = None

    for line in lines:
        line = line.rstrip("\r\n")

        if not line:
            # Пустая строка означает завершение формирования события
            if data_buffer or current_event != "message":
                event_data = "\n".join(data_buffer)
                yield SseEvent(
                    event=current_event,
                    data=event_data,
                    event_id=current_id,
                    retry=current_retry,
                )
            # Сброс буфера для следующего события
            current_event = "message"
            data_buffer = []
            continue

        if line.startswith(":"):
            # Комментарий SSE — игнорируем
            continue

        if ":" in line:
            field, _, value = line.partition(":")
            field = field.strip()
            if value.startswith(" "):
                value = value[1:]

            if field == "event":
                current_event = value
            elif field == "data":
                data_buffer.append(value)
            elif field == "id":
                current_id = value
            elif field == "retry":
                try:
                    current_retry = int(value)
                except ValueError:
                    pass
        else:
            field = line.strip()
            if field == "event":
                current_event = ""
            elif field == "data":
                data_buffer.append("")


class SseConfigClient:
    """
    Клиент для постоянного подключения к SSE-серверу обновлений конфигурации.

    Запускает отдельный фоновый поток, читающий события из соединения,
    и вызывает зарегистрированные колбэки при получении обновлений.
    """

    def __init__(
        self,
        url: str,
        on_event: Callable[[SseEvent], None] | None = None,
        on_reload: Callable[[], None] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
    ) -> None:
        """
        Инициализирует SSE-клиент.

        Args:
            url: URL SSE-эндпоинта.
            on_event: Колбэк, вызываемый при получении любого SSE события.
            on_reload: Колбэк без аргументов, вызываемый для перезагрузки конфига.
            headers: Дополнительные HTTP-заголовки (например, для аутентификации).
            timeout: Таймаут для сетевых операций в секундах.
            reconnect_delay: Начальная задержка переподключения в секундах.
            max_reconnect_delay: Максимальная задержка переподключения в секундах.
        """
        self.url = url
        self.on_event = on_event
        self.on_reload = on_reload
        self.headers = headers or {}
        self.timeout = timeout
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_event_id: str | None = None

    @property
    def is_running(self) -> bool:
        """Возвращает True, если фоновый поток клиента запущен и работает."""
        return self._thread is not None and self._thread.is_alive()

    def _create_request(self) -> urllib.request.Request:
        """
        Создает объект HTTP-запроса с соответствующими заголовками SSE.

        Returns:
            Сформированный urllib.request.Request.
        """
        req = urllib.request.Request(self.url)
        req.add_header("Accept", "text/event-stream")
        req.add_header("Cache-Control", "no-cache")

        if self._last_event_id:
            req.add_header("Last-Event-ID", self._last_event_id)

        for key, val in self.headers.items():
            req.add_header(key, val)

        return req

    def start(self) -> None:
        """Запускает фоновый поток SSE-клиента."""
        if self.is_running:
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="SseConfigClientThread",
            daemon=True,
        )
        self._thread.start()
        logger.debug("SSE-клиент запущен для %s", self.url)

    def stop(self) -> None:
        """Останавливает фоновый поток SSE-клиента."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.debug("SSE-клиент остановлен для %s", self.url)

    def _worker(self) -> None:
        """Основной цикл фонового потока подключения и переподключения."""
        current_delay = self.reconnect_delay

        while not self._stop_event.is_set():
            try:
                self._connect_and_stream()
                # При успешном открытии и чтении соединение завершилось чисто
                current_delay = self.reconnect_delay
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                logger.warning(
                    "Ошибка в SSE-клиенте (%s): %s. Повтор через %.2f сек.",
                    self.url,
                    exc,
                    current_delay,
                )

            # Экспоненциальная задержка перед следующей попыткой
            wait_remains = current_delay
            while wait_remains > 0 and not self._stop_event.is_set():
                step = min(0.1, wait_remains)
                self._stop_event.wait(step)
                wait_remains -= step

            current_delay = min(current_delay * 2.0, self.max_reconnect_delay)

    def _connect_and_stream(self) -> None:
        """Подключается к SSE эндпоинту и считывает события."""
        req = self._create_request()

        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            lines_generator = self._read_lines(response)
            for event in parse_sse_lines(lines_generator):
                if self._stop_event.is_set():
                    break

                if event.event_id:
                    self._last_event_id = event.event_id

                if event.retry is not None:
                    self.reconnect_delay = event.retry / 1000.0

                if self.on_event:
                    try:
                        self.on_event(event)
                    except Exception as err:
                        logger.error("Ошибка в обработчике on_event SSE: %s", err)

                if self.on_reload:
                    try:
                        self.on_reload()
                    except Exception as err:
                        logger.error("Ошибка в обработчике on_reload SSE: %s", err)

    def _read_lines(self, response: object) -> Iterator[str]:
        """Считывает строки из ответа сервера по мере их поступления."""
        while not self._stop_event.is_set():
            line_bytes = getattr(response, "readline")()
            if not line_bytes:
                break
            yield line_bytes.decode("utf-8")
