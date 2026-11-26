"""Тесты тестового репозитория, DFS, фильтрации и циклов."""

from collections import OrderedDict

import pytest

from depviz.errors import ConfigError
from depviz.graph import (build_graph, build_maven_graph, format_graph,
                          read_test_repository, repository_dependencies)
from depviz.maven import Coordinates, EffectiveModel, Exclusion


def loader(graph):
    """Создать функцию зависимостей из словаря."""
    return lambda package: graph.get(package, [])


def test_recursive_dfs_and_shared_dependencies():
    """Общий пакет посещается один раз, транзитивные связи сохраняются."""
    source = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    graph = build_graph("A", loader(source))
    assert list(graph) == ["A", "B", "D", "C"]
    assert graph["C"] == ["D"]


def test_cycle_does_not_recurse_forever():
    """Цикл A-B-C-A обрабатывается без бесконечной рекурсии."""
    source = {"A": ["B"], "B": ["C"], "C": ["A"]}
    graph = build_graph("A", loader(source))
    assert graph == {"A": ["B"], "B": ["C"], "C": ["A"]}


def test_filter_excludes_package_and_its_subtree():
    """Отфильтрованный пакет не раскрывается и не попадает в граф."""
    source = {"A": ["AB", "C"], "AB": ["D"], "C": ["D"], "D": []}
    graph = build_graph("A", loader(source), "B")
    assert graph == {"A": ["C"], "C": ["D"], "D": []}


def test_filtered_root_is_an_error():
    """Исключение корня считается ошибкой конфигурации анализа."""
    with pytest.raises(ConfigError, match="корневой пакет"):
        build_graph("ABC", loader({"ABC": []}), "B")


def test_read_test_repository(tmp_path):
    """Читаются пустые зависимости, комментарии и порядок пакетов."""
    path = tmp_path / "repo.txt"
    path.write_text("# graph\nA: B C\nB:\nC: B\n", encoding="utf-8")
    assert read_test_repository(str(path)) == OrderedDict([
        ("A", ["B", "C"]), ("B", []), ("C", ["B"])
    ])


@pytest.mark.parametrize("text", ["a: B\n", "A B\n", "A: b\n"])
def test_invalid_test_repository(tmp_path, text):
    """Некорректные имена и синтаксис дают ошибку с номером строки."""
    path = tmp_path / "repo.txt"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="строка 1"):
        read_test_repository(str(path))


def test_missing_package_error():
    """Ссылка на неизвестный пакет не игнорируется."""
    dependencies = repository_dependencies({"A": ["B"]})
    with pytest.raises(ConfigError, match="отсутствует"):
        dependencies("B")


def test_format_graph():
    """Изолированный пакет выводится без стрелки."""
    assert format_graph({"A": ["B"], "B": []}) == "A -> B\nB"


def test_maven_nearest_wins_and_transitive_exclusions(monkeypatch):
    """Ближайшая версия заменяет глубокую, исключённый узел не загружается."""
    root = Coordinates("g", "app", "1")
    b1 = Coordinates("g", "b", "1",
                     exclusions=(Exclusion("g", "excluded"),))
    b2 = Coordinates("g", "b", "2")
    x = Coordinates("g", "x", "1")
    c = Coordinates("g", "c", "1")
    d1 = Coordinates("g", "d", "1")
    d2 = Coordinates("g", "d", "2")
    excluded = Coordinates("g", "excluded", "1")
    models = {
        str(root): [x, b2, d2],
        str(x): [b1, c],
        str(b1): [d1, excluded],
        str(b2): [],
        str(c): [d1],
        str(d1): [],
        str(d2): [],
    }

    def load(repository, package, cache):
        return EffectiveModel(None, {}, {}, models[str(package)])

    monkeypatch.setattr("depviz.graph.load_effective_model", load)
    graph = build_maven_graph("repo", root)
    assert set(graph) == {root, x, b2, c, d2}
    assert graph[b2] == []
    assert graph[x] == [b2, c]
    assert graph[c] == [d2]
    assert graph[root] == [x, b2, d2]


def test_optional_is_direct_only_for_analyzed_root(monkeypatch):
    """Optional корня включается, а транзитивный optional пропускается."""
    root = Coordinates("g", "app", "1")
    direct = Coordinates("g", "direct", "1", optional=True)
    child = Coordinates("g", "child", "1")
    hidden = Coordinates("g", "hidden", "1", optional=True)
    models = {str(root): [direct, child], str(direct): [],
              str(child): [hidden], str(hidden): []}

    def load(repository, package, cache):
        return EffectiveModel(None, {}, {}, models[str(package)])

    monkeypatch.setattr("depviz.graph.load_effective_model", load)
    graph = build_maven_graph("repo", root)
    assert graph == {root: [direct, child], direct: [], child: []}


def test_root_dependency_management_controls_transitive_versions(monkeypatch):
    """Управление версиями корня распространяется на весь граф."""
    root = Coordinates("g", "app", "1")
    child = Coordinates("g", "child", "1")
    transitive1 = Coordinates("g", "lib", "1")
    transitive2 = Coordinates("g", "lib", "2")
    models = {
        str(root): EffectiveModel(None, {}, {"g:lib": "2"}, [child]),
        str(child): EffectiveModel(None, {}, {}, [transitive1]),
        str(transitive2): EffectiveModel(None, {}, {}, []),
    }
    monkeypatch.setattr("depviz.graph.load_effective_model",
                        lambda repository, package, cache: models[str(package)])
    graph = build_maven_graph("repo", root)
    assert graph == {root: [child], child: [transitive2], transitive2: []}
