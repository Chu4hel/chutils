from __future__ import annotations


class MockServerRunner:
    """Заглушка класса MockServerRunner для фазы 1."""

    def __init__(
            self,
            port: int = 8888,
            routes_path: str = "mocks.yml",
            proxy_fallback: str | None = None,
    ) -> None:
        self.port = port
        self.routes_path = routes_path
        self.proxy_fallback = proxy_fallback

    def init_template(self, output_path: str) -> None:
        """Инициализировать шаблонный файл роутов."""
        pass

    def run(self) -> None:
        """Запустить мок-сервер."""
        pass
