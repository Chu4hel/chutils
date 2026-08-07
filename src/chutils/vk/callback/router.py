"""VKCallbackRouter — легковесный обработчик Callback API (Webhook) VK Ботов."""

import inspect
import os
from typing import Any, Callable, Coroutine

from chutils.exceptions.base import ChutilsException


class VKCallbackError(ChutilsException):
    """Исключение при обработке VK Callback API события."""

    pass


class VKCallbackRouter:
    """Маршрутизатор событий VK Callback API.

    Автоматически подтверждает сервер (confirmation_code), проверяет секретный ключ (secret_key)
    и диспатчит входящие события по зарегистрированным хэндлерам.
    """

    def __init__(
        self,
        confirmation_code: str | None = None,
        secret_key: str | None = None,
        path: str = "/vk-callback",
    ) -> None:
        """Инициализирует VKCallbackRouter.

        Args:
            confirmation_code: Строка подтверждения сервера ВКонтакте.
            secret_key: Секретный ключ группы для проверки authenticity.
            path: HTTP путь вебхука в приложениях FastAPI / Starlette.
        """
        self.confirmation_code = confirmation_code or self._resolve_confirmation_code()
        self.secret_key = secret_key or self._resolve_secret_key()
        self.path = path

        self._event_handlers: dict[str, list[Callable[..., Any]]] = {}
        self._unhandled_handler: Callable[..., Any] | None = None

    @staticmethod
    def _resolve_confirmation_code() -> str | None:
        """Поиск confirmation_code через secret_manager / config / env."""
        try:
            from chutils.secret_manager import SecretManager
            sm = SecretManager()
            for key in ("vk_confirmation_code", "CH_VK_CONFIRMATION_CODE"):
                val = sm.get_secret(key)
                if val:
                    return val
        except Exception:
            pass

        for env_key in ("VK_CONFIRMATION_CODE", "CH_VK_CONFIRMATION_CODE"):
            val = os.getenv(env_key)
            if val:
                return val

        return None

    @staticmethod
    def _resolve_secret_key() -> str | None:
        """Поиск secret_key группы через secret_manager / config / env."""
        try:
            from chutils.secret_manager import SecretManager
            sm = SecretManager()
            for key in ("vk_secret_key", "CH_VK_SECRET_KEY"):
                val = sm.get_secret(key)
                if val:
                    return val
        except Exception:
            pass

        for env_key in ("VK_SECRET_KEY", "CH_VK_SECRET_KEY"):
            val = os.getenv(env_key)
            if val:
                return val

        return None

    def on_event(self, event_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Декоратор подписки на тип события VK Callback API (например, 'message_new').

        Args:
            event_type: Строковое имя типа события VK API.

        Returns:
            Декоратор функции-обработчика.
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(func)
            return func

        return decorator

    def on_message_new(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Алиас декоратора для события 'message_new'."""
        return self.on_event("message_new")(func)

    def on_wall_post_new(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Алиас декоратора для события 'wall_post_new'."""
        return self.on_event("wall_post_new")(func)

    def on_unhandled_event(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Декоратор для обработки незарегистрированных типов событий."""
        self._unhandled_handler = func
        return func

    async def handle_event(self, event_data: dict[str, Any]) -> str:
        """Обрабатывает входящее событие VK Callback API.

        Args:
            event_data: Словарь запроса VK Callback API.

        Returns:
            Текст ответа (confirmation_code или "ok").

        Raises:
            VKCallbackError: Если проверка secret_key не пройдена.
        """
        event_type = event_data.get("type")
        secret = event_data.get("secret")

        # Проверка secret_key, если он задан
        if self.secret_key and secret != self.secret_key:
            raise VKCallbackError(
                "Недействительный секретный ключ (secret) в событии VK Callback API.",
                hint="Проверьте совпадение secret_key группы VK и настроек приложения."
            )

        # Тип запроса confirmation -> вернуть confirmation_code
        if event_type == "confirmation":
            if not self.confirmation_code:
                raise VKCallbackError(
                    "Получен запрос 'confirmation', но confirmation_code не задан.",
                    hint="Укажите confirmation_code в VKCallbackRouter или через VK_CONFIRMATION_CODE."
                )
            return self.confirmation_code

        # Вызов зарегистрированных обработчиков
        handlers = self._event_handlers.get(str(event_type), [])
        if not handlers and self._unhandled_handler:
            handlers = [self._unhandled_handler]

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as exc:
                # Логируем ошибку, но не заваливаем ответ "ok" для VK
                import logging
                logging.getLogger("chutils.vk.callback").error(
                    f"Ошибка при выполнении хэндлера {handler.__name__} для события {event_type}: {exc}"
                )

        return "ok"

    def get_fastapi_router(self) -> Any:
        """Создает и возвращает настроенный FastAPI APIRouter.

        Returns:
            Экземпляр fastapi.APIRouter.
        """
        try:
            from fastapi import APIRouter, HTTPException, Request, Response
        except ImportError:
            raise RuntimeError("FastAPI не установлен. Установите fastapi или chutils[vk].")

        fastapi_router = APIRouter()

        @fastapi_router.post(self.path)
        async def vk_callback_endpoint(request: Request) -> Response:
            try:
                body = await request.json()
            except Exception as exc:
                raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

            try:
                res_text = await self.handle_event(body)
                return Response(content=res_text, media_type="text/plain")
            except VKCallbackError as exc:
                raise HTTPException(status_code=403, detail=exc.message) from exc

        return fastapi_router
