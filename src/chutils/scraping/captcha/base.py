import importlib.util

from chutils.exceptions import ChutilsConfigurationError, OptionalDependencyError


def _ensure_httpx() -> None:
    if importlib.util.find_spec("httpx") is None:
        raise OptionalDependencyError(
            "Модуль 'httpx' не установлен. Для работы с капча-клиентами "
            "установите его: pip install chutils[captcha] или pip install httpx.",
            dependency="httpx",
            hint="Выполните pip install chutils[captcha] или pip install httpx."
        )


class BaseCaptchaSolver:
    """Базовый синхронный клиент для сервисов решения капч."""
    secret_key_name: str = ""

    def __init__(self, api_key: str | None = None) -> None:
        _ensure_httpx()
        self.api_key = api_key or self._get_secret_key()
        if not self.api_key:
            raise ChutilsConfigurationError(
                f"API-ключ для {self.__class__.__name__} не задан. "
                f"Передайте его явно или установите в secret_manager как {self.secret_key_name}."
            )

    def _get_secret_key(self) -> str | None:
        if not self.secret_key_name:
            return None
        from chutils.secret_manager import SecretManager
        try:
            sm = SecretManager("")
            return sm.get_secret(self.secret_key_name)
        except Exception:
            return None


class BaseAsyncCaptchaSolver:
    """Базовый асинхронный клиент для сервисов решения капч."""
    secret_key_name: str = ""

    def __init__(self, api_key: str | None = None) -> None:
        _ensure_httpx()
        self.api_key = api_key or self._get_secret_key()
        if not self.api_key:
            raise ChutilsConfigurationError(
                f"API-ключ для {self.__class__.__name__} не задан. "
                f"Передайте его явно или установите в secret_manager как {self.secret_key_name}."
            )

    def _get_secret_key(self) -> str | None:
        if not self.secret_key_name:
            return None
        from chutils.secret_manager import SecretManager
        try:
            sm = SecretManager("")
            return sm.get_secret(self.secret_key_name)
        except Exception:
            return None
