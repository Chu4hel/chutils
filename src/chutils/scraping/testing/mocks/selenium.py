"""Синхронный мок Selenium WebDriver и WebElement для оффлайн-тестирования."""

from typing import TYPE_CHECKING

from chutils.scraping.testing.mocks.dom import DOMNode, parse_html_dom


class MockSeleniumElement:
    """Мок веб-элемента Selenium WebElement."""

    def __init__(self, node: DOMNode) -> None:
        """Инициализирует мок элемента Selenium.

        Args:
            node: Внутренний узел DOMNode.
        """
        self._node: DOMNode = node

    @property
    def text(self) -> str:
        """Возвращает видимый текст элемента.

        Returns:
            Текст элемента.
        """
        return self._node.text

    @property
    def tag_name(self) -> str:
        """Возвращает имя тега элемента.

        Returns:
            Имя тега.
        """
        return self._node.tag

    def get_attribute(self, name: str) -> str | None:
        """Возвращает значение атрибута.

        Args:
            name: Имя атрибута.

        Returns:
            Значение атрибута или None.
        """
        return self._node.attrs.get(name)

    def find_element(self, by: str, value: str) -> "MockSeleniumElement":
        """Находит первый вложенный элемент по указанному селектору.

        Args:
            by: Стратегия поиска (css selector, id, xpath и т.д.).
            value: Значение селектора.

        Returns:
            Экземпляр MockSeleniumElement.

        Raises:
            ValueError: Если элемент не найден.
        """
        selector = _normalize_selector(by, value)
        node = self._node.select(selector)
        if node is None:
            raise ValueError(f"Элемент не найден: {by}={value}")
        return MockSeleniumElement(node)

    def find_elements(self, by: str, value: str) -> list["MockSeleniumElement"]:
        """Находит все вложенные элементы по указанному селектору.

        Args:
            by: Стратегия поиска.
            value: Значение селектора.

        Returns:
            Список MockSeleniumElement.
        """
        selector = _normalize_selector(by, value)
        nodes = self._node.select_all(selector)
        return [MockSeleniumElement(n) for n in nodes]

    def click(self) -> None:
        """Имитирует клик по элементу."""
        pass

    def send_keys(self, keys: str) -> None:
        """Имитирует ввод текста в элемент.

        Args:
            keys: Вводимый текст.
        """
        self._node.attrs["value"] = keys

    def is_displayed(self) -> bool:
        """Проверяет отображение элемента.

        Returns:
            True, если элемент присутствует.
        """
        return True


class MockSeleniumDriver:
    """Синхронный мок Selenium WebDriver для автономного тестирования."""

    def __init__(self, html: str, url: str = "about:blank") -> None:
        """Инициализирует мок драйвера Selenium.

        Args:
            html: HTML-код страницы.
            url: Начальный URL.
        """
        self._html: str = html
        self.current_url: str = url
        self._root: DOMNode = parse_html_dom(html)

    @property
    def page_source(self) -> str:
        """Возвращает исходный код страницы.

        Returns:
            HTML-код страницы.
        """
        return self._html

    @property
    def title(self) -> str:
        """Возвращает заголовок страницы.

        Returns:
            Текст из тега title или пустая строка.
        """
        title_node = self._root.select("title")
        return title_node.text if title_node else ""

    def get(self, url: str) -> None:
        """Имитирует переход по URL.

        Args:
            url: Целевой URL.
        """
        self.current_url = url

    def find_element(self, by: str, value: str) -> MockSeleniumElement:
        """Находит первый элемент на странице.

        Args:
            by: Стратегия поиска (например, 'css selector', 'id').
            value: Селектор.

        Returns:
            Найденный элемент MockSeleniumElement.

        Raises:
            ValueError: Если элемент не найден.
        """
        selector = _normalize_selector(by, value)
        node = self._root.select(selector)
        if node is None:
            raise ValueError(f"Элемент не найден: {by}={value}")
        return MockSeleniumElement(node)

    def find_elements(self, by: str, value: str) -> list[MockSeleniumElement]:
        """Находит все подходящие элементы на странице.

        Args:
            by: Стратегия поиска.
            value: Селектор.

        Returns:
            Список найденных элементов MockSeleniumElement.
        """
        selector = _normalize_selector(by, value)
        nodes = self._root.select_all(selector)
        return [MockSeleniumElement(n) for n in nodes]

    def execute_script(self, script: str, *args: object) -> object:
        """Имитирует выполнение скрипта.

        Args:
            script: Строка JavaScript.
            args: Передаваемые аргументы.

        Returns:
            Результат выполнения.
        """
        if "return document.title" in script:
            return self.title
        return None


def _normalize_selector(by: str, value: str) -> str:
    """Нормализует стратегию By в CSS-селектор."""
    by_lower = by.lower()
    if by_lower in ("css selector", "css"):
        return value
    if by_lower == "id":
        return f"#{value}"
    if by_lower in ("class name", "class"):
        return f".{value}"
    if by_lower in ("tag name", "tag"):
        return value
    return value
