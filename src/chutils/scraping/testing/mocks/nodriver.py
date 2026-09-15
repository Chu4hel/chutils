"""Мок реализации вкладки nodriver.Tab и элементов nodriver.Element."""

from chutils.scraping.testing.mocks.dom import DOMNode, parse_html_dom


class MockNodriverElement:
    """Мок HTML-элемента в стиле nodriver.Element."""

    def __init__(self, node: DOMNode) -> None:
        """Инициализирует мок элемента.

        Args:
            node: Внутренний узел DOMNode.
        """
        self._node: DOMNode = node

    @property
    def text(self) -> str:
        """Возвращает текстовое содержимое элемента."""
        return self._node.text

    @property
    def attrs(self) -> dict[str, str]:
        """Возвращает словарь атрибутов элемента."""
        return dict(self._node.attrs)

    @property
    def tag(self) -> str:
        """Возвращает имя тега элемента."""
        return self._node.tag

    async def select(self, selector: str) -> "MockNodriverElement | None":
        """Находит первый дочерний элемент по CSS-селектору.

        Args:
            selector: CSS-селектор.

        Returns:
            Экземпляр MockNodriverElement или None.
        """
        node = self._node.select(selector)
        return MockNodriverElement(node) if node is not None else None

    async def select_all(self, selector: str) -> list["MockNodriverElement"]:
        """Находит все дочерние элементы по CSS-селектору.

        Args:
            selector: CSS-селектор.

        Returns:
            Список найденных элементов MockNodriverElement.
        """
        nodes = self._node.select_all(selector)
        return [MockNodriverElement(n) for n in nodes]

    async def click(self) -> None:
        """Имитирует клик по элементу (no-op)."""

    async def send_keys(self, text: str) -> None:
        """Имитирует ввод текста в элемент.

        Args:
            text: Вводимый текст.
        """
        self._node.attrs["value"] = text


class MockNodriverTab:
    """Мок вкладки браузера nodriver.Tab для автономного тестирования парсеров."""

    def __init__(self, html: str, url: str = "about:blank") -> None:
        """Инициализирует мок вкладки nodriver.

        Args:
            html: HTML-содержимое страницы.
            url: URL страницы.
        """
        self._html: str = html
        self.url: str = url
        self._root: DOMNode = parse_html_dom(html)

    async def get_content(self) -> str:
        """Возвращает исходный HTML страницы.

        Returns:
            HTML-код страницы.
        """
        return self._html

    async def select(self, selector: str) -> MockNodriverElement | None:
        """Находит первый элемент по CSS-селектору.

        Args:
            selector: CSS-селектор.

        Returns:
            Экземпляр MockNodriverElement или None.
        """
        node = self._root.select(selector)
        return MockNodriverElement(node) if node is not None else None

    async def select_all(self, selector: str) -> list[MockNodriverElement]:
        """Находит все элементы по CSS-селектору.

        Args:
            selector: CSS-селектор.

        Returns:
            Список элементов MockNodriverElement.
        """
        nodes = self._root.select_all(selector)
        return [MockNodriverElement(n) for n in nodes]

    async def find(self, text: str) -> MockNodriverElement | None:
        """Находит наиболее специфичный элемент, содержащий указанный текст.

        Args:
            text: Искомая подстрока.

        Returns:
            Найденный элемент MockNodriverElement или None.
        """
        candidates: list[DOMNode] = []
        for desc in self._root._collect_descendants():
            if text in desc.text:
                candidates.append(desc)
        if candidates:
            candidates.sort(key=lambda d: len(d.text))
            return MockNodriverElement(candidates[0])
        return None

    async def evaluate(self, expression: str) -> object:
        """Имитирует выполнение простого JavaScript выражения.

        Args:
            expression: Строка выражения (например, document.title).

        Returns:
            Результат выполнения выражения.
        """
        expr = expression.strip()
        if "document.title" in expr:
            title_node = self._root.select("title")
            return title_node.text if title_node else ""
        if "window.location" in expr:
            return self.url
        return None

    async def sleep(self, seconds: float = 0.0) -> None:
        """Имитирует ожидание (no-op в тестах).

        Args:
            seconds: Количество секунд.
        """
