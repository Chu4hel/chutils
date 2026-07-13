import random

DEFAULT_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]


class UserAgentRotator:
    """Класс для ротации HTTP-заголовков User-Agent.

    Поддерживает случайный выбор или Round-Robin обход списка заголовков.
    """

    def __init__(
            self, user_agents: list[str] | None = None, fallback: str | None = None
    ) -> None:
        """Инициализирует ротатор User-Agent.

        Args:
            user_agents: Список строк User-Agent. Если None, используется список по умолчанию.
            fallback: Резервный User-Agent, если список пуст.
        """
        self.user_agents: list[str] = (
            user_agents
            if user_agents is not None
            else list(DEFAULT_USER_AGENTS)
        )
        self.fallback: str = fallback or (
            DEFAULT_USER_AGENTS[0] if DEFAULT_USER_AGENTS else ""
        )
        self._index: int = 0

    def get(self, strategy: str = "random") -> str:
        """Возвращает следующий User-Agent согласно выбранной стратегии.

        Args:
            strategy: Стратегия ротации ('random' или 'round_robin').

        Returns:
            Строка User-Agent.

        Raises:
            ValueError: Если передан неизвестный тип стратегии.
        """
        if not self.user_agents:
            return self.fallback

        if strategy == "random":
            return random.choice(self.user_agents)
        elif strategy == "round_robin":
            ua = self.user_agents[self._index]
            self._index = (self._index + 1) % len(self.user_agents)
            return ua
        else:
            raise ValueError(
                f"Неизвестная стратегия ротации: {strategy}. Ожидалось 'random' или 'round_robin'."
            )
