"""Мок реализации Playwright Page и Locator для оффлайн-тестирования."""

from chutils.scraping.testing.mocks.dom import DOMNode, parse_html_dom


class MockPlaywrightLocator:
    """Мок Playwright Locator, инкапсулирующий один или несколько найденных узлов."""

    def __init__(self, nodes: list[DOMNode]) -> None:
        """Инициализирует локатор списком узлов.

        Args:
            nodes: Список узлов DOMNode.
        """
        self._nodes: list[DOMNode] = nodes

    def locator(self, selector: str) -> "MockPlaywrightLocator":
        """Возвращает вложенный локатор относительно текущих узлов.

        Args:
            selector: CSS-селектор.

        Returns:
            Экземпляр MockPlaywrightLocator.
        """
        collected: list[DOMNode] = []
        for n in self._nodes:
            collected.extend(n.select_all(selector))
        return MockPlaywrightLocator(collected)

    async def count(self) -> int:
        """Возвращает количество найденных элементов.

        Returns:
            Число элементов в выборке локатора.
        """
        return len(self._nodes)

    async def all(self) -> list["MockPlaywrightLocator"]:
        """Возвращает список локаторов для каждого отдельного элемента.

        Returns:
            Список MockPlaywrightLocator.
        """
        return [MockPlaywrightLocator([n]) for n in self._nodes]

    @property
    def first(self) -> "MockPlaywrightLocator":
        """Возвращает первый элемент выборки.

        Returns:
            MockPlaywrightLocator с первым узлом.
        """
        return (
            MockPlaywrightLocator([self._nodes[0]])
            if self._nodes
            else MockPlaywrightLocator([])
        )

    @property
    def last(self) -> "MockPlaywrightLocator":
        """Возвращает последний элемент выборки.

        Returns:
            MockPlaywrightLocator с последним узлом.
        """
        return (
            MockPlaywrightLocator([self._nodes[-1]])
            if self._nodes
            else MockPlaywrightLocator([])
        )

    def nth(self, index: int) -> "MockPlaywrightLocator":
        """Возвращает n-й элемент выборки.

        Args:
            index: Индекс элемента (0-based).

        Returns:
            MockPlaywrightLocator для n-го узла.
        """
        if 0 <= index < len(self._nodes):
            return MockPlaywrightLocator([self._nodes[index]])
        return MockPlaywrightLocator([])

    async def inner_text(self) -> str:
        """Возвращает видимый текст первого элемента.

        Returns:
            Текст элемента.
        """
        if not self._nodes:
            raise ValueError("Элемент не найден для inner_text()")
        return self._nodes[0].text

    async def text_content(self) -> str | None:
        """Возвращает текстовое содержимое элемента.

        Returns:
            Текст элемента или None.
        """
        if not self._nodes:
            return None
        return self._nodes[0].text

    async def get_attribute(self, name: str) -> str | None:
        """Возвращает значение атрибута первого элемента.

        Args:
            name: Имя атрибута.

        Returns:
            Значение атрибута или None.
        """
        if not self._nodes:
            return None
        return self._nodes[0].attrs.get(name)

    async def is_visible(self) -> bool:
        """Проверяет видимость элемента.

        Returns:
            True, если элемент присутствует в DOM.
        """
        return bool(self._nodes)

    async def click(self) -> None:
        """Имитирует клик (no-op)."""

    async def fill(self, value: str) -> None:
        """Имитирует заполнение поля значением.

        Args:
            value: Вводимое значение.
        """
        if self._nodes:
            self._nodes[0].attrs["value"] = value


class MockPlaywrightPage:
    """Мок объекта playwright.async_api.Page для автономного тестирования парсеров."""

    def __init__(self, html: str, url: str = "about:blank") -> None:
        """Инициализирует мок страницы Playwright.

        Args:
            html: HTML-содержимое страницы.
            url: URL страницы.
        """
        self._html: str = html
        self.url: str = url
        self._root: DOMNode = parse_html_dom(html)

    def locator(self, selector: str) -> MockPlaywrightLocator:
        """Возвращает объект Locator по указанному селектору.

        Args:
            selector: CSS-селектор.

        Returns:
            Экземпляр MockPlaywrightLocator.
        """
        nodes = self._root.select_all(selector)
        return MockPlaywrightLocator(nodes)

    async def title(self) -> str:
        """Возвращает заголовок страницы (title).

        Returns:
            Текст из тега title или пустая строка.
        """
        node = self._root.select("title")
        return node.text if node else ""

    async def content(self) -> str:
        """Возвращает HTML-код страницы.

        Returns:
            Исходный HTML.
        """
        return self._html

    async def evaluate(self, expression: str, arg: object = None) -> object:
        """Имитирует выполнение простого JS выражения.

        Args:
            expression: Выражение JS.
            arg: Опциональный аргумент.

        Returns:
            Результат выражения.
        """
        if "document.title" in expression:
            return await self.title()
        return None

    async def goto(self, url: str) -> None:
        """Имитирует переход по URL.

        Args:
            url: Целевой адрес.
        """
        self.url = url
