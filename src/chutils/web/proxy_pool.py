import random
import threading
import time
import urllib.request
from typing import Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from chutils.logger import ChutilsLogger

_module_logger: Optional["ChutilsLogger"] = None


def _get_logger() -> "ChutilsLogger":
    global _module_logger
    if _module_logger is None:
        from chutils.logger import setup_logger
        _module_logger = setup_logger(__name__)
    return _module_logger


class ProxyPool:
    """Класс для управления пулом прокси-серверов.

    Поддерживает статический список, получение прокси из системных переменных окружения,
    загрузку списка по URL и фоновое обновление по таймеру.
    """

    def __init__(
            self,
            proxies: Sequence[str] | None = None,
            url: str | None = None,
            update_interval: float | None = None,
            use_env: bool = False,
            strategy: str = "random",
    ) -> None:
        """Инициализирует пул прокси.

        Args:
            proxies: Статический список прокси-серверов.
            url: URL для загрузки прокси-листа в формате плейн-текст (один прокси на строку).
            update_interval: Интервал обновления списка по URL в секундах.
            use_env: Использовать ли системные прокси из переменных окружения.
            strategy: Стратегия ротации ('random' или 'round_robin').
        """
        self.url: str | None = url
        self.update_interval: float | None = update_interval
        self.use_env: bool = use_env
        self.strategy: str = strategy

        self._proxies: list[str] = list(proxies) if proxies is not None else []
        self._lock: threading.Lock = threading.Lock()
        self._index: int = 0

        self._stop_event: threading.Event = threading.Event()
        self._update_thread: threading.Thread | None = None

        # Инициализируем прокси
        if self.use_env:
            self._load_env_proxies()

        if self.url:
            self.update_from_url()

    def _load_env_proxies(self) -> None:
        """Загружает прокси из системных переменных окружения."""
        try:
            env_dict = urllib.request.getproxies()
            env_list: list[str] = []
            for scheme in ["all", "https", "http"]:
                if scheme in env_dict:
                    val = env_dict[scheme]
                    if val and val not in env_list:
                        env_list.append(val)

            with self._lock:
                for p in env_list:
                    if p not in self._proxies:
                        self._proxies.append(p)
        except Exception as e:
            _get_logger().warning("Не удалось загрузить прокси из окружения: %s", e)

    def update_from_url(self) -> None:
        """Загружает список прокси с указанного URL."""
        if not self.url:
            return

        try:
            req = urllib.request.Request(
                self.url,
                headers={
                    "User-Agent": "Mozilla/5.0 chutils.web ProxyPool Updater"
                },
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                content: str = response.read().decode("utf-8")

            new_proxies: list[str] = []
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                new_proxies.append(line)

            with self._lock:
                self._proxies = new_proxies
                self._index = 0
            _get_logger().info("Пул прокси успешно обновлен с URL. Загружено: %d", len(new_proxies))
        except Exception as e:
            _get_logger().warning("Сбой при обновлении прокси с URL %s: %s", self.url, e)

    def start_background_update(self) -> None:
        """Запускает фоновый поток для периодического обновления прокси."""
        if not self.url or not self.update_interval:
            return

        with self._lock:
            if self._update_thread and self._update_thread.is_alive():
                return
            self._stop_event.clear()
            self._update_thread = threading.Thread(
                target=self._run_updater, daemon=True, name="ChutilsProxyUpdater"
            )
            self._update_thread.start()

    def stop_background_update(self) -> None:
        """Останавливает фоновый поток обновления прокси."""
        self._stop_event.set()
        if self._update_thread:
            self._update_thread.join(timeout=5)
            self._update_thread = None

    def _run_updater(self) -> None:
        """Внутренний цикл фонового обновления."""
        interval = self.update_interval or 300.0
        while not self._stop_event.is_set():
            # Спим частями по 0.1 секунды, чтобы быстро реагировать на stop_event
            elapsed = 0.0
            while elapsed < interval and not self._stop_event.is_set():
                time.sleep(0.1)
                elapsed += 0.1

            if not self._stop_event.is_set():
                self.update_from_url()

    def get_next_proxy(self) -> str | None:
        """Возвращает следующий прокси-сервер согласно выбранной стратегии.

        Returns:
            Строка прокси или None, если пул пуст.
        """
        with self._lock:
            if not self._proxies:
                return None

            if self.strategy == "random":
                return random.choice(self._proxies)
            elif self.strategy == "round_robin":
                if self._index >= len(self._proxies):
                    self._index = 0
                proxy = self._proxies[self._index]
                self._index = (self._index + 1) % len(self._proxies)
                return proxy
            else:
                # Если стратегия невалидна, возвращаем случайный прокси
                return random.choice(self._proxies)

    def get_all_proxies(self) -> list[str]:
        """Возвращает копию текущего списка прокси.

        Returns:
            Список строк прокси.
        """
        with self._lock:
            return list(self._proxies)
