"""Pytest fixtures и моки для тестирования приложений VK и VKMA."""

from contextlib import contextmanager
from typing import Any, Callable, Generator
from unittest.mock import MagicMock, patch

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

from chutils.vk.testing.generators import generate_fake_launch_params, generate_fake_user


class MockVKApi:
    """Мок для имитации вызовов VK API (например, users.get, messages.send)."""

    def __init__(self) -> None:
        self.responses: dict[str, Any] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def register_response(self, method: str, response_data: Any) -> None:
        """Регистрирует ответы для вызова метода VK API.

        Args:
            method: Имя метода VK API.
            response_data: Данные ответа для возврата.
        """
        self.responses[method] = response_data

    def call(self, method: str, **kwargs: Any) -> Any:
        """Имитирует вызов метода VK API.

        Args:
            method: Имя вызываемого метода.
            **kwargs: Произвольные параметры вызова.

        Returns:
            Ответ метода VK API.
        """
        self.calls.append((method, kwargs))
        if method in self.responses:
            return self.responses[method]

        # Дефолтные мок-ответы для частых методов
        if method == "users.get":
            user_id = kwargs.get("user_ids", 123456)
            if isinstance(user_id, list):
                user_id = user_id[0] if user_id else 123456
            return [generate_fake_user(user_id=int(user_id))]
        if method == "messages.send":
            return 10001

        return {"status": "ok"}


@contextmanager
def mock_vk_api_context() -> Generator[MockVKApi, None, None]:
    """Контекстный менеджер для мокирования вызовов VK API.

    Returns:
        Генератор с объектом MockVKApi.
    """
    mock = MockVKApi()
    yield mock


if HAS_PYTEST:
    @pytest.fixture
    def vk_launch_params_factory() -> Callable[..., str]:
        """Pytest фикстура-фабрика для генерации поддельных launchParams VKMA.

        Returns:
            Фабричная функция генерации launchParams.
        """
        def _factory(
            user_id: int = 123456,
            app_id: int = 77777,
            secret_key: str = "test_secret_key",
            expired: bool = False,
            tampered: bool = False,
            extra_params: dict[str, Any] | None = None,
        ) -> str:
            return generate_fake_launch_params(
                user_id=user_id,
                app_id=app_id,
                secret_key=secret_key,
                expired=expired,
                tampered=tampered,
                extra_params=extra_params,
            )

        return _factory

    @pytest.fixture
    def mock_vk_api() -> Generator[MockVKApi, None, None]:
        """Pytest фикстура для перехвата вызовов VK API.

        Returns:
            Генератор мока VK API.
        """
        with mock_vk_api_context() as mock:
            yield mock
else:
    vk_launch_params_factory = None  # type: ignore[assignment]
    mock_vk_api = None  # type: ignore[assignment]
