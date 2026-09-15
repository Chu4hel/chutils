"""Легковесное DOM-дерево и парсер HTML для мокирования браузерных страниц."""

import re
from html.parser import HTMLParser


class DOMNode:
    """Узел легковесного DOM-дерева."""

    def __init__(
        self,
        tag: str,
        attrs: dict[str, str],
        parent: "DOMNode | None" = None,
    ) -> None:
        """Инициализирует узел DOM.

        Args:
            tag: Название тега.
            attrs: Словарь HTML-атрибутов.
            parent: Родительский узел или None для корня.
        """
        self.tag: str = tag.lower()
        self.attrs: dict[str, str] = attrs
        self.children: list[DOMNode] = []
        self.parent: DOMNode | None = parent
        self._direct_text: list[str] = []

    @property
    def text(self) -> str:
        """Возвращает весь видимый текстовый контент узла и его потомков.

        Returns:
            Строка с объединенным текстовым контентом.
        """
        collected: list[str] = []

        def _walk(node: DOMNode) -> None:
            for chunk in node._direct_text:
                cleaned = chunk.strip()
                if cleaned:
                    collected.append(cleaned)
            for child in node.children:
                _walk(child)

        _walk(self)
        return " ".join(collected)

    def select(self, selector: str) -> "DOMNode | None":
        """Находит первый узел, соответствующий CSS селектору.

        Args:
            selector: CSS селектор.

        Returns:
            Найденный узел DOMNode или None.
        """
        results = self.select_all(selector)
        return results[0] if results else None

    def select_all(self, selector: str) -> list["DOMNode"]:
        """Находит все узлы, соответствующие CSS селектору.

        Args:
            selector: CSS селектор.

        Returns:
            Список найденных узлов DOMNode.
        """
        tokens = [t.strip() for t in selector.split() if t.strip()]
        if not tokens:
            return []

        current_set = self._collect_descendants()
        for token in tokens:
            if token == ">":
                continue
            matched: list[DOMNode] = []
            for node in current_set:
                if _matches_simple_selector(node, token):
                    matched.append(node)
            current_set = []
            for m in matched:
                current_set.extend(m._collect_descendants())
            if not tokens:
                return matched
        # Фильтруем результаты относительно исходного корня
        final_results: list[DOMNode] = []
        for cand in self._collect_descendants():
            if (
                _matches_compound_selector(cand, selector, self)
                and cand not in final_results
            ):
                final_results.append(cand)
        return final_results

    def _collect_descendants(self) -> list["DOMNode"]:
        """Рекурсивно собирает всех потомков узла."""
        descendants: list[DOMNode] = []

        def _walk(node: DOMNode) -> None:
            for child in node.children:
                descendants.append(child)
                _walk(child)

        _walk(self)
        return descendants


def _matches_simple_selector(node: DOMNode, selector: str) -> bool:
    """Проверяет совпадение простого селектора (тег, id, класс, атрибуты)."""
    # 1. ID selector: #id
    if selector.startswith("#"):
        return node.attrs.get("id") == selector[1:]

    # 2. Class selector: .class
    if selector.startswith("."):
        cls = selector[1:]
        node_classes = node.attrs.get("class", "").split()
        return cls in node_classes

    # 3. Attribute selector: [attr] or [attr="val"]
    attr_match = re.match(r"^\[([a-zA-Z0-9_-]+)(?:=[\"']?(.*?)[\"']?)?\]$", selector)
    if attr_match:
        attr_name = attr_match.group(1)
        expected_val = attr_match.group(2)
        if attr_name not in node.attrs:
            return False
        if expected_val is not None:
            return node.attrs[attr_name] == expected_val
        return True

    # 4. Tag with class or id: e.g. a.btn or h1#header or div.product-card
    tag_match = re.match(
        r"^([a-zA-Z0-9]+)?(?:#([a-zA-Z0-9_-]+))?(?:\.([a-zA-Z0-9_.-]+))?$", selector
    )
    if tag_match:
        tag_name, elem_id, class_names = tag_match.groups()
        if tag_name and node.tag != tag_name.lower():
            return False
        if elem_id and node.attrs.get("id") != elem_id:
            return False
        if class_names:
            req_classes = class_names.split(".")
            node_classes = node.attrs.get("class", "").split()
            if not all(c in node_classes for c in req_classes if c):
                return False
        return True

    return False


def _matches_compound_selector(
    node: DOMNode, selector: str, root_scope: DOMNode
) -> bool:
    """Проверяет соответствие узла составному селектору (включая цепочки предков)."""
    parts = [p.strip() for p in selector.split() if p.strip()]
    if not parts:
        return False

    if not _matches_simple_selector(node, parts[-1]):
        return False

    if len(parts) == 1:
        return True

    # Проверяем цепочку предков
    curr_node = node.parent
    part_idx = len(parts) - 2

    while curr_node is not None and curr_node != root_scope.parent and part_idx >= 0:
        if _matches_simple_selector(curr_node, parts[part_idx]):
            part_idx -= 1
        curr_node = curr_node.parent

    return part_idx < 0


class _TreeBuilder(HTMLParser):
    """Парсер HTML для построения дерева DOMNode."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: DOMNode = DOMNode(tag="html_root", attrs={})
        self._stack: list[DOMNode] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Обрабатывает открывающий HTML тег и создает узел в DOM.

        Args:
            tag: Имя тега.
            attrs: Список пар атрибутов (имя, значение).
        """
        attr_dict = {k: v or "" for k, v in attrs}
        parent = self._stack[-1]
        node = DOMNode(tag=tag, attrs=attr_dict, parent=parent)
        parent.children.append(node)
        # Самозакрывающиеся теги не добавляем в стек
        void_tags = {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
        if tag.lower() not in void_tags:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        """Обрабатывает закрывающий HTML тег, схлопывая стек.

        Args:
            tag: Имя закрываемого тега.
        """
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag.lower():
                self._stack = self._stack[:i]
                break

    def handle_data(self, data: str) -> None:
        """Обрабатывает текстовые фрагменты внутри текущего узла.

        Args:
            data: Текстовые данные.
        """
        if self._stack:
            self._stack[-1]._direct_text.append(data)


def parse_html_dom(html_content: str) -> DOMNode:
    """Парсит HTML-строку и возвращает корневой узел DOM.

    Args:
        html_content: Сырая строка HTML.

    Returns:
        Корневой узел DOMNode.
    """
    builder = _TreeBuilder()
    builder.feed(html_content)
    return builder.root
