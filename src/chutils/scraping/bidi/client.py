"""Клиент протокола WebDriver BiDi на основе WebSockets."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from chutils.logger import setup_logger
from chutils.scraping.bidi.exceptions import (
    BiDiCommandError,
    BiDiConnectionError,
    BiDiTimeoutError,
)

if TYPE_CHECKING:
    import websockets.asyncio.client

logger = setup_logger(__name__)

EventHandler = Callable[[dict[str, object]], Awaitable[None] | None]


class BiDiClient:
    """Асинхронный клиент для взаимодействия с браузером по протоколу WebDriver BiDi.

    Позволяет отправлять JSON-RPC команды стандартизированного протокола WebDriver BiDi,
    получать ответы и подписываться на асинхронные события браузера.
    """

    def __init__(self, ws_url: str) -> None:
        """Инициализирует BiDiClient.

        Args:
            ws_url: WebSocket URL конечной точки WebDriver BiDi.
        """
        self.ws_url = ws_url
        self._ws: websockets.asyncio.client.ClientConnection | None = None
        self._command_id: int = 0
        self._pending_commands: dict[int, asyncio.Future[dict[str, object]]] = {}
        self._event_listeners: dict[str, list[EventHandler]] = defaultdict(list)
        self._listen_task: asyncio.Task[None] | None = None
        self._is_closed: bool = False

    @property
    def is_connected(self) -> bool:
        """Проверяет, активно ли соединение с браузером."""
        return self._ws is not None and not self._is_closed

    async def connect(self) -> None:
        """Устанавливает соединение с WebSocket эндпоинтом WebDriver BiDi.

        Raises:
            BiDiConnectionError: Если не удалось установить соединение.
            ImportError: Если библиотека websockets не установлена.
        """
        try:
            import websockets
        except ImportError as err:
            raise ImportError(
                "Для работы с WebDriver BiDi необходимо установить websockets: "
                "pip install websockets или pip install chutils[bidi]"
            ) from err

        try:
            self._ws = await websockets.connect(self.ws_url)
            self._is_closed = False
            self._listen_task = asyncio.create_task(self._listen_loop())
            logger.debug("Установлено соединение WebDriver BiDi с %s", self.ws_url)
        except Exception as exc:
            raise BiDiConnectionError(f"Не удалось подключиться к WebDriver BiDi по адресу {self.ws_url}: {exc}") from exc

    async def close(self) -> None:
        """Закрывает соединение с WebDriver BiDi и останавливает фоновые задачи."""
        self._is_closed = True

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        for fut in self._pending_commands.values():
            if not fut.done():
                fut.set_exception(BiDiConnectionError("Соединение закрыто до получения ответа"))
        self._pending_commands.clear()

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception as exc:
                logger.debug("Ошибка при закрытии WebSocket: %s", exc)
            finally:
                self._ws = None

    async def send_command(
        self,
        method: str,
        params: dict[str, object] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, object]:
        """Отправляет команду браузеру и ожидает ответ.

        Args:
            method: Имя метода WebDriver BiDi (например, 'session.new', 'browsingContext.navigate').
            params: Параметры команды.
            timeout: Максимальное время ожидания ответа в секундах.

        Returns:
            Словарь с результатом выполнения команды (содержимое поля 'result').

        Raises:
            BiDiConnectionError: Если клиент не подключен к браузеру.
            BiDiTimeoutError: При истечении таймаута ожидания ответа.
            BiDiCommandError: Если браузер вернул ошибку выполнения команды.
        """
        if not self.is_connected or self._ws is None:
            raise BiDiConnectionError("BiDiClient не подключен. Сначала вызовите connect().")

        self._command_id += 1
        cmd_id = self._command_id

        payload: dict[str, object] = {
            "id": cmd_id,
            "method": method,
            "params": params or {},
        }

        fut: asyncio.Future[dict[str, object]] = asyncio.get_running_loop().create_future()
        self._pending_commands[cmd_id] = fut

        try:
            await self._ws.send(json.dumps(payload))
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError as err:
            self._pending_commands.pop(cmd_id, None)
            raise BiDiTimeoutError(f"Превышен таймаут {timeout}с ожидания команды '{method}' (id={cmd_id})") from err
        except Exception:
            self._pending_commands.pop(cmd_id, None)
            raise

    def on(self, event_name: str, handler: EventHandler) -> None:
        """Регистрирует обработчик события WebDriver BiDi.

        Args:
            event_name: Имя события (например, 'browsingContext.load') или '*' для всех событий.
            handler: Синхронная или асинхронная функция-обработчик.
        """
        self._event_listeners[event_name].append(handler)

    def remove_listener(self, event_name: str, handler: EventHandler) -> None:
        """Удаляет зарегистрированный обработчик события.

        Args:
            event_name: Имя события.
            handler: Функция-обработчик для удаления.
        """
        listeners = self._event_listeners.get(event_name)
        if listeners and handler in listeners:
            listeners.remove(handler)

    async def _listen_loop(self) -> None:
        """Фоновый цикл приема сообщений из WebSocket."""
        assert self._ws is not None
        try:
            async for raw_message in self._ws:
                try:
                    data = json.loads(raw_message)
                    await self._dispatch_message(data)
                except Exception:
                    logger.exception("Ошибка при обработке сообщения BiDi")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("WebSocket BiDi соединение завершено с ошибкой: %s", exc)
        finally:
            self._is_closed = True

    async def _dispatch_message(self, message: dict[str, object]) -> None:
        """Диспетчеризирует полученное сообщение (ответ на команду или событие).

        Args:
            message: Распарсенное JSON-сообщение.
        """
        cmd_id = message.get("id")
        if isinstance(cmd_id, int) and cmd_id in self._pending_commands:
            fut = self._pending_commands.pop(cmd_id)
            if fut.done():
                return

            msg_type = message.get("type")
            if msg_type == "error" or "error" in message:
                err_code = str(message.get("error", "unknown error"))
                err_msg = str(message.get("message", ""))
                err_data = message.get("data")
                data_dict = err_data if isinstance(err_data, dict) else None
                fut.set_exception(BiDiCommandError(err_code, err_msg, data_dict))
            else:
                raw_result = message.get("result")
                result_dict = raw_result if isinstance(raw_result, dict) else {}
                fut.set_result(result_dict)
            return

        msg_type = message.get("type")
        method = message.get("method")
        if msg_type == "event" or isinstance(method, str):
            event_name = str(method) if method else ""
            raw_params = message.get("params")
            params = raw_params if isinstance(raw_params, dict) else {}
            await self._trigger_event(event_name, params)

    async def _trigger_event(self, event_name: str, params: dict[str, object]) -> None:
        """Вызывает подписчиков на указанное событие.

        Args:
            event_name: Имя события.
            params: Параметры события.
        """
        handlers = list(self._event_listeners.get(event_name, [])) + list(self._event_listeners.get("*", []))
        for handler in handlers:
            try:
                res = handler(params)
                if inspect.isawaitable(res):
                    await res
            except Exception:
                logger.exception("Ошибка в обработчике события BiDi '%s'", event_name)

    # ---------------------------------------------------------
    # Высокоуровневые методы протокола WebDriver BiDi
    # ---------------------------------------------------------

    async def session_new(
        self,
        capabilities: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Создает новую сессию WebDriver BiDi (метод session.new).

        Args:
            capabilities: Словарь настроек capabilities.

        Returns:
            Результат выполнения session.new (содержит sessionId и capabilities).
        """
        params: dict[str, object] = {
            "capabilities": capabilities or {"alwaysMatch": {}},
        }
        return await self.send_command("session.new", params)

    async def session_subscribe(
        self,
        events: list[str],
        contexts: list[str] | None = None,
    ) -> dict[str, object]:
        """Подписывается на указанные события WebDriver BiDi.

        Args:
            events: Список имен событий (например, ['browsingContext.load']).
            contexts: Опциональный список идентификаторов контекстов.

        Returns:
            Результат выполнения session.subscribe.
        """
        params: dict[str, object] = {"events": events}
        if contexts is not None:
            params["contexts"] = contexts
        return await self.send_command("session.subscribe", params)

    async def session_unsubscribe(
        self,
        events: list[str],
        contexts: list[str] | None = None,
    ) -> dict[str, object]:
        """Отписывается от указанных событий WebDriver BiDi.

        Args:
            events: Список имен событий.
            contexts: Опциональный список идентификаторов контекстов.

        Returns:
            Результат выполнения session.unsubscribe.
        """
        params: dict[str, object] = {"events": events}
        if contexts is not None:
            params["contexts"] = contexts
        return await self.send_command("session.unsubscribe", params)

    async def browsing_context_get_tree(
        self,
        max_depth: int | None = None,
        root: str | None = None,
    ) -> list[dict[str, object]]:
        """Возвращает дерево контекстов браузера (вкладок/фреймов).

        Args:
            max_depth: Максимальная глубина обхода дерева.
            root: Корневой контекст (если None, возвращаются все корневые контексты).

        Returns:
            Список словарей с описанием контекстов браузера.
        """
        params: dict[str, object] = {}
        if max_depth is not None:
            params["maxDepth"] = max_depth
        if root is not None:
            params["root"] = root
        res = await self.send_command("browsingContext.getTree", params)
        raw_contexts = res.get("contexts", [])
        return raw_contexts if isinstance(raw_contexts, list) else []

    async def browsing_context_navigate(
        self,
        context: str,
        url: str,
        wait: str = "complete",
    ) -> dict[str, object]:
        """Выполняет переход по указанному URL в заданном контексте.

        Args:
            context: Идентификатор контекста браузера.
            url: Целевой URL.
            wait: Стратегия ожидания готовности страницы ('none', 'interactive', 'complete').

        Returns:
            Результат навигации (содержит navigationId и url).
        """
        params: dict[str, object] = {
            "context": context,
            "url": url,
            "wait": wait,
        }
        return await self.send_command("browsingContext.navigate", params)

    async def browsing_context_create(
        self,
        type: str = "tab",
        reference_context: str | None = None,
    ) -> dict[str, object]:
        """Создает новый контекст браузера (вкладку или окно).

        Args:
            type: Тип контекста ('tab' или 'window').
            reference_context: Опциональный ссылочный контекст.

        Returns:
            Результат создания контекста (содержит contextId).
        """
        params: dict[str, object] = {"type": type}
        if reference_context is not None:
            params["referenceContext"] = reference_context
        return await self.send_command("browsingContext.create", params)

    async def browsing_context_close(
        self,
        context: str,
    ) -> dict[str, object]:
        """Закрывает указанный контекст браузера.

        Args:
            context: Идентификатор контекста для закрытия.

        Returns:
            Результат выполнения browsingContext.close.
        """
        params: dict[str, object] = {"context": context}
        return await self.send_command("browsingContext.close", params)

    async def script_evaluate(
        self,
        expression: str,
        target: dict[str, object],
        await_promise: bool = True,
        result_ownership: str = "none",
    ) -> dict[str, object]:
        """Вычисляет JavaScript выражение в целевом контексте.

        Args:
            expression: Строка JavaScript выражения.
            target: Словарь целевого контекста (например, {'context': context_id}).
            await_promise: Ожидать ли разрешение промиса (по умолчанию True).
            result_ownership: Политика владения объектами ('none' или 'root').

        Returns:
            Результат вычисления (содержит type, value и т.д.).
        """
        params: dict[str, object] = {
            "expression": expression,
            "target": target,
            "awaitPromise": await_promise,
            "resultOwnership": result_ownership,
        }
        return await self.send_command("script.evaluate", params)

    async def script_call_function(
        self,
        function_declaration: str,
        target: dict[str, object],
        arguments: list[dict[str, object]] | None = None,
        await_promise: bool = True,
        result_ownership: str = "none",
    ) -> dict[str, object]:
        """Вызывает JavaScript функцию в целевом контексте.

        Args:
            function_declaration: Определение функции (например, '() => window.innerWidth').
            target: Словарь целевого контекста.
            arguments: Список аргументов функции.
            await_promise: Ожидать ли промис.
            result_ownership: Политика владения объектами.

        Returns:
            Результат вызова функции.
        """
        params: dict[str, object] = {
            "functionDeclaration": function_declaration,
            "target": target,
            "awaitPromise": await_promise,
            "resultOwnership": result_ownership,
        }
        if arguments is not None:
            params["arguments"] = arguments
        return await self.send_command("script.callFunction", params)

    async def script_add_preload_script(
        self,
        function_declaration: str,
        arguments: list[dict[str, object]] | None = None,
        contexts: list[str] | None = None,
        sandbox: str | None = None,
    ) -> str:
        """Добавляет скрипт предварительной загрузки (Preload Script).

        Скрипт предзагрузки выполняется до загрузки DOM во всех вновь создаваемых документах,
        что является ключевым механизмом антидетекта в WebDriver BiDi.

        Args:
            function_declaration: Функция для вызова перед загрузкой страницы.
            arguments: Аргументы функции.
            contexts: Опциональный список контекстов.
            sandbox: Имя изолированной песочницы (по умолчанию None — основной контекст окна).

        Returns:
            Идентификатор зарегистрированного скрипта (script id).
        """
        params: dict[str, object] = {
            "functionDeclaration": function_declaration,
        }
        if arguments is not None:
            params["arguments"] = arguments
        if contexts is not None:
            params["contexts"] = contexts
        if sandbox is not None:
            params["sandbox"] = sandbox

        res = await self.send_command("script.addPreloadScript", params)
        return str(res.get("script", ""))

    async def script_remove_preload_script(
        self,
        script: str,
    ) -> dict[str, object]:
        """Удаляет ранее зарегистрированный скрипт предзагрузки.

        Args:
            script: Идентификатор скрипта.

        Returns:
            Результат удаления скрипта.
        """
        params: dict[str, object] = {"script": script}
        return await self.send_command("script.removePreloadScript", params)
