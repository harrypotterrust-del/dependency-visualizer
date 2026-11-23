"""Тесты тестового репозитория, DFS, фильтрации и циклов."""

from collections import OrderedDict

import pytest

from depviz.errors import ConfigError
from depviz.graph import (build_graph, format_graph, read_test_repository,
                          repository_dependencies)


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
