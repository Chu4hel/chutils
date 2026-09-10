"""
Механизм сохранения и воспроизведения HTML-снапшотов (оффлайн-фикстур) страниц.

Позволяет сохранять дампы страниц реальных веб-сайтов один раз и воспроизводить
их мгновенно в unit-тестах в виде чистого HTML или моков nodriver, Playwright и Selenium.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import TracebackType
from typing import Any, Literal
from typing_extensions import Self

from chutils.fs import atomic_write, ensure_dir
from chutils.logger import setup_logger
from chutils.scraping.testing.mocks import (
    MockNodriverTab,
    MockPlaywrightPage,
    MockSeleniumDriver,
)

logger = setup_logger(__name__)

MockType = Literal["raw", "nodriver", "playwright", "selenium"]
FetcherType = Callable[[], str | Awaitable[str]]


class SnapshotRecorder:
    """Менеджер сохранения и загрузки оффлайн-снапшотов HTML страниц."""

    def __init__(self, snapshot_dir: Path | str | None = None) -> None:
        """Инициализирует менеджер снапшотов.

        Args:
            snapshot_dir: Каталог для хранения HTML файлов. По умолчанию
                'tests/fixtures/snapshots'.
        """
        if snapshot_dir is not None:
            self.snapshot_dir = Path(snapshot_dir).resolve()
        else:
            self.snapshot_dir = Path("tests/fixtures/snapshots").resolve()

    def _resolve_path(self, name: str) -> Path:
        """Формирует путь к файлу снапшота.

        Args:
            name: Имя снапшота.

        Returns:
            Объект Path к файлу снапшота.
        """
        filename = name if name.endswith(".html") else f"{name}.html"
        return self.snapshot_dir / filename

    def exists(self, name: str) -> bool:
        """Проверяет, существует ли сохраненный снапшот.

        Args:
            name: Имя снапшота.

        Returns:
            True, если файл снапшота существует, иначе False.
        """
        return self._resolve_path(name).is_file()

    def save(self, name: str, html: str) -> Path:
        """Сохраняет HTML-содержимое в файл снапшота.

        Args:
            name: Имя снапшота.
            html: HTML разметка для сохранения.

        Returns:
            Абсолютный путь к сохраненному файлу снапшота.
        """
        ensure_dir(self.snapshot_dir)
        target_file = self._resolve_path(name)
        atomic_write(target_file, data=html, mode="w", encoding="utf-8")
        logger.debug("Снапшот '%s' успешно сохранен в %s", name, target_file)
        return target_file

    def load(self, name: str) -> str:
        """Загружает содержимое сохраненного снапшота.

        Args:
            name: Имя снапшота.

        Returns:
            HTML содержимое сохраненной страницы.

        Raises:
            FileNotFoundError: Если файл снапшота не найден на диске.
        """
        target_file = self._resolve_path(name)
        if not target_file.is_file():
            raise FileNotFoundError(
                f"HTML-снапшот '{name}' не найден по пути: {target_file}. "
                "Запустите тест в режиме записи (record=True) для создания фикстуры."
            )
        return target_file.read_text(encoding="utf-8")


class use_html_snapshot:
    """Контекстный менеджер и декоратор для воспроизведения/записи снапшотов страниц."""

    def __init__(
        self,
        name: str,
        snapshot_dir: Path | str | None = None,
        as_mock: MockType = "raw",
        fetcher: FetcherType | None = None,
        record: bool = False,
    ) -> None:
        """Инициализирует контекстный менеджер/декоратор снапшота.

        Args:
            name: Идентификатор/имя файла снапшота.
            snapshot_dir: Каталог сохранения снапшотов.
            as_mock: Формат возвращаемого объекта ('raw', 'nodriver', 'playwright', 'selenium').
            fetcher: Функция получения страницы при отсутствии снапшота или record=True.
            record: Принудительно выполнить fetcher и обновить снапшот на диске.
        """
        self.name = name
        self.as_mock = as_mock
        self.fetcher = fetcher
        self.record = record
        self.recorder = SnapshotRecorder(snapshot_dir=snapshot_dir)
        self._target_obj: Any = None

    def _wrap_mock(self, html: str) -> Any:
        """Преобразует HTML строку в указанный тип мок-объекта.

        Args:
            html: Исходная разметка страницы.

        Returns:
            Сырая строка HTML или экземпляр мока страницы.
        """
        if self.as_mock == "nodriver":
            return MockNodriverTab(html)
        if self.as_mock == "playwright":
            return MockPlaywrightPage(html)
        if self.as_mock == "selenium":
            return MockSeleniumDriver(html)
        return html

    def _get_or_record_sync(self) -> str:
        """Синхронно загружает или записывает снапшот.

        Returns:
            HTML содержимое.
        """
        if self.recorder.exists(self.name) and not self.record:
            return self.recorder.load(self.name)

        if self.fetcher is None:
            return self.recorder.load(self.name)

        res = self.fetcher()
        if inspect.isawaitable(res):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                # Если уже внутри loop, создаем задачу в потоке
                html = asyncio.run_coroutine_threadsafe(res, loop).result()
            else:
                html = asyncio.run(res)
        else:
            html = str(res)

        self.recorder.save(self.name, html)
        return html

    async def _get_or_record_async(self) -> str:
        """Асинхронно загружает или записывает снапшот.

        Returns:
            HTML содержимое.
        """
        if self.recorder.exists(self.name) and not self.record:
            return self.recorder.load(self.name)

        if self.fetcher is None:
            return self.recorder.load(self.name)

        res = self.fetcher()
        if inspect.isawaitable(res):
            html = await res
        else:
            html = str(res)

        self.recorder.save(self.name, html)
        return html

    def __enter__(self) -> Any:
        """Вход в синхронный контекстный менеджер.

        Returns:
            HTML разметка или инкапсулированный мок браузера.
        """
        html = self._get_or_record_sync()
        self._target_obj = self._wrap_mock(html)
        return self._target_obj

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Выход из контекстного менеджера.

        Args:
            exc_type: Тип исключения (если возникло).
            exc_val: Экземпляр исключения.
            exc_tb: Трассировка стека.
        """
        pass

    async def __aenter__(self) -> Any:
        """Вход в асинхронный контекстный менеджер.

        Returns:
            HTML разметка или инкапсулированный мок браузера.
        """
        html = await self._get_or_record_async()
        self._target_obj = self._wrap_mock(html)
        return self._target_obj

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Выход из асинхронного контекстного менеджера.

        Args:
            exc_type: Тип исключения.
            exc_val: Экземпляр исключения.
            exc_tb: Трассировка стека.
        """
        pass

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Декорирует синхронную или асинхронную тестовую функцию.

        Args:
            fn: Целевая тестовая функция.

        Returns:
            Обернутая функция, принимающая объект страницы первым аргументом.
        """
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                async with self as target:
                    return await fn(target, *args, **kwargs)

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with self as target:
                return fn(target, *args, **kwargs)

        return sync_wrapper
