"""Тесты разворота репозитория и обратных зависимостей."""

from depviz.graph import build_graph, invert_repository, repository_dependencies


def test_invert_repository():
    """Каждая связь A -> B превращается в B -> A."""
    assert invert_repository({"A": ["B", "C"], "B": [], "C": ["B"]}) == {
        "A": [], "B": ["A", "C"], "C": ["A"]
    }


def test_reverse_dependencies_use_recursive_dfs():
    """Находятся прямые и транзитивные потребители заданного пакета."""
    source = {"A": ["B"], "B": ["D"], "C": ["D"], "D": []}
    inverted = invert_repository(source)
    graph = build_graph("D", repository_dependencies(inverted))
    assert graph == {"D": ["B", "C"], "B": ["A"], "C": [], "A": []}


def test_reverse_cycle():
    """Обратный обход также безопасен при цикле."""
    inverted = invert_repository({"A": ["B"], "B": ["A"]})
    graph = build_graph("A", repository_dependencies(inverted))
    assert graph == {"A": ["B"], "B": ["A"]}
