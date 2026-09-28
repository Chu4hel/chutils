"""Высокоуровневая сессия WebDriver BiDi и контекстные менеджеры."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Self

from chutils.logger import setup_logger
from chutils.scraping.bidi.client import BiDiClient
from chutils.scraping.bidi.exceptions import BiDiError

logger = setup_logger(__name__)


def extract_bidi_url(target: str | object) -> str:
    """Извлекает WebSocket URL для WebDriver BiDi из строки или объекта браузерного драйвера.

    Поддерживает:
    - Прямую строку WebSocket URL ('ws://...' или 'wss://...').
    - Экземпляр Selenium WebDriver со свойством capabilities['webSocketUrl'].
    - Объект соединения driver.bidi_connection.

    Args:
        target: URL в виде строки или объект драйвера Selenium/WebDriver.

    Returns:
        WebSocket URL для подключения.

    Raises:
        ValueError: Если URL не удалось извлечь или он имеет неверный формат.
    """
    if isinstance(target, str):
        url = target.strip()
        if not url.startswith(("ws://", "wss://")):
            raise ValueError(f"Недопустимый протокол WebSocket URL: {target}. Ожидалось ws:// или wss://")
        return url

    # Проверка Selenium 4 driver.bidi_connection
    if hasattr(target, "bidi_connection"):
        conn = getattr(target, "bidi_connection")
        if isinstance(conn, str) and conn.startswith(("ws://", "wss://")):
            return conn
        url_attr = getattr(conn, "url", None) or getattr(conn, "ws_url", None)
        if isinstance(url_attr, str) and url_attr.startswith(("ws://", "wss://")):
            return url_attr

    # Проверка driver.capabilities
    if hasattr(target, "capabilities") and isinstance(target.capabilities, dict):
        caps = target.capabilities
        # Стандарт W3C BiDi
        ws_url = caps.get("webSocketUrl")
        if isinstance(ws_url, str) and ws_url:
            return ws_url

        # Chrome DevTools / BiDi address
        chrome_opts = caps.get("goog:chromeOptions")
        if isinstance(chrome_opts, dict):
            dbg_addr = chrome_opts.get("debuggerAddress")
            if isinstance(dbg_addr, str) and dbg_addr:
                return f"ws://{dbg_addr}/devtools/browser"

    raise ValueError(
        f"Не удалось извлечь WebDriver BiDi WebSocket URL из объекта {type(target).__name__}. "
        "Убедитесь, что драйвер запущен с опцией webSocketUrl: True или передан валидный URL ws://."
    )


class BiDiSession:
    """Высокоуровневая сессия для управления браузером через WebDriver BiDi.

    Обеспечивает управление контекстами (вкладками), навигацию, выполнение
    JavaScript-скриптов и внедрение скриптов предзагрузки для антидетекта.
    """

    def __init__(
        self,
        endpoint_or_driver: str | object,
        *,
        auto_create_session: bool = False,
    ) -> None:
        """Инициализирует сессию BiDi.

        Args:
            endpoint_or_driver: WebSocket URL либо экземпляр Selenium WebDriver.
            auto_create_session: Вызывать ли session.new при подключении (нужно при прямом
                подключении к браузеру без предшествующего классического WebDriver).
        """
        self.ws_url = extract_bidi_url(endpoint_or_driver)
        self.client = BiDiClient(self.ws_url)
        self.auto_create_session = auto_create_session
        self.session_id: str | None = None
        self.active_context_id: str | None = None

    async def __aenter__(self) -> Self:
        """Асинхронно подключается к браузеру и инициализирует сессию."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Закрывает соединение с браузером."""
        await self.close()

    async def start(self) -> None:
        """Устанавливает соединение и определяет текущий активный контекст."""
        await self.client.connect()

        if self.auto_create_session:
            res = await self.client.session_new()
            raw_sid = res.get("sessionId")
            if isinstance(raw_sid, str):
                self.session_id = raw_sid

        # Получаем первичное дерево контекстов
        try:
            contexts = await self.client.browsing_context_get_tree(max_depth=0)
            if contexts:
                first_ctx = contexts[0].get("context")
                if isinstance(first_ctx, str):
                    self.active_context_id = first_ctx
        except Exception as exc:
            logger.debug("Не удалось получить начальное дерево контекстов: %s", exc)

    async def close(self) -> None:
        """Завершает сессию и закрывает WebSocket клиент."""
        await self.client.close()

    async def get_contexts(self) -> list[dict[str, object]]:
        """Возвращает список всех активных контекстов верхнего уровня.

        Returns:
            Список контекстов браузера.
        """
        return await self.client.browsing_context_get_tree(max_depth=0)

    async def new_tab(self) -> str:
        """Создает новую вкладку и переключает на нее active_context_id.

        Returns:
            Идентификатор созданного контекста (вкладки).
        """
        res = await self.client.browsing_context_create(type="tab")
        context_id = str(res.get("context", ""))
        if context_id:
            self.active_context_id = context_id
        return context_id

    async def close_tab(self, context_id: str | None = None) -> None:
        """Закрывает вкладку браузера.

        Args:
            context_id: Идентификатор контекста. Если None, закрывается active_context_id.
        """
        target = context_id or self.active_context_id
        if not target:
            raise BiDiError("Не указан идентификатор контекста для закрытия")

        await self.client.browsing_context_close(target)
        if target == self.active_context_id:
            contexts = await self.get_contexts()
            self.active_context_id = str(contexts[0].get("context", "")) if contexts else None

    async def navigate(
        self,
        url: str,
        context_id: str | None = None,
        wait: str = "complete",
    ) -> dict[str, object]:
        """Осуществляет переход по адресу URL.

        Args:
            url: Целевой адрес.
            context_id: Опциональный идентификатор контекста.
            wait: Стратегия ожидания ('none', 'interactive', 'complete').

        Returns:
            Словарь с данными навигации.
        """
        target = context_id or self.active_context_id
        if not target:
            # Если активный контекст неизвестен, пробуем получить его
            contexts = await self.get_contexts()
            if contexts:
                target = str(contexts[0].get("context", ""))
                self.active_context_id = target
            else:
                target = await self.new_tab()

        return await self.client.browsing_context_navigate(context=target, url=url, wait=wait)

    async def evaluate(
        self,
        expression: str,
        context_id: str | None = None,
        await_promise: bool = True,
    ) -> dict[str, object]:
        """Выполняет JavaScript выражение в контексте страницы.

        Args:
            expression: Строка JavaScript кода.
            context_id: Опциональный контекст (по умолчанию активный).
            await_promise: Ожидать ли промис.

        Returns:
            Полный ответ script.evaluate.
        """
        target = context_id or self.active_context_id
        if not target:
            raise BiDiError("Нет активного контекста для выполнения JavaScript")
        return await self.client.script_evaluate(
            expression=expression,
            target={"context": target},
            await_promise=await_promise,
        )

    async def evaluate_value(
        self,
        expression: str,
        context_id: str | None = None,
    ) -> object:
        """Вычисляет выражение и извлекает распакованное примитивное значение.

        Args:
            expression: JavaScript выражение.
            context_id: Идентификатор контекста.

        Returns:
            Значение из поля 'value' дескриптора результата BiDi, либо None.
        """
        res = await self.evaluate(expression, context_id=context_id)
        result_payload = res.get("result")
        if isinstance(result_payload, dict):
            return result_payload.get("value")
        return None

    async def add_preload_script(
        self,
        function_declaration: str,
        arguments: list[dict[str, object]] | None = None,
        contexts: list[str] | None = None,
        sandbox: str | None = None,
    ) -> str:
        """Добавляет скрипт предзагрузки для всей сессии или выбранных контекстов.

        Args:
            function_declaration: Тело функции скрипта.
            arguments: Аргументы.
            contexts: Опциональный фильтр контекстов.
            sandbox: Песочница.

        Returns:
            Идентификатор зарегистрированного скрипта (script id).
        """
        return await self.client.script_add_preload_script(
            function_declaration=function_declaration,
            arguments=arguments,
            contexts=contexts,
            sandbox=sandbox,
        )

    async def remove_preload_script(self, script_id: str) -> dict[str, object]:
        """Удаляет скрипт предзагрузки по идентификатору.

        Args:
            script_id: Идентификатор скрипта.

        Returns:
            Результат удаления.
        """
        return await self.client.script_remove_preload_script(script_id)


@asynccontextmanager
async def bidi_session(
    endpoint_or_driver: str | object,
    *,
    auto_create_session: bool = False,
) -> AsyncIterator[BiDiSession]:
    """Асинхронный контекстный менеджер для работы с сессией WebDriver BiDi.

    Example:
        ```python
        async with bidi_session("ws://localhost:9222/session/123") as session:
            await session.navigate("https://example.com")
            title = await session.evaluate_value("document.title")
        ```

    Args:
        endpoint_or_driver: WebSocket URL или Selenium WebDriver.
        auto_create_session: Создавать ли новую сессию BiDi.

    Yields:
        Инициализированная сессия BiDiSession.
    """
    session = BiDiSession(endpoint_or_driver, auto_create_session=auto_create_session)
    async with session:
        yield session
