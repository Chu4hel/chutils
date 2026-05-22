import json

from chutils.dev.models import ProjectIndex, Node, Symbol, Breadcrumbs, GraphEdge


def test_project_index_serialization():
    """Тест сериализации корневого объекта индекса в JSON."""

    # Готовим тестовые данные
    root_node = Node(
        name="chutils",
        path="src/chutils",
        type="package",
        layer="public",
        children=[
            Node(
                name="config",
                path="src/chutils/config",
                type="package",
                symbols=[
                    Symbol(
                        name="get_config",
                        type="function",
                        breadcrumbs=Breadcrumbs(is_async=False, tags=["core"])
                    )
                ]
            )
        ]
    )

    edge = GraphEdge(source="src/chutils/logger", target="src/chutils/config", weight=5)

    index = ProjectIndex(root=root_node, dependency_graph=[edge])

    # Сериализуем
    json_str = index.model_dump_json(indent=2)
    data = json.loads(json_str)

    # Проверяем структуру
    assert data["project_name"] == "chutils"
    assert data["root"]["name"] == "chutils"
    assert len(data["root"]["children"]) == 1
    assert data["root"]["children"][0]["name"] == "config"
    assert data["root"]["children"][0]["symbols"][0]["name"] == "get_config"
    assert data["dependency_graph"][0]["weight"] == 5
