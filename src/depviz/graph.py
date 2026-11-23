"""Тестовый репозиторий и рекурсивный DFS графа зависимостей."""

import re
from collections import OrderedDict

from depviz.errors import ConfigError
from depviz.maven import load_model, parse_coordinates, parse_dependency
from depviz.maven import child, children, resolve_version

PACKAGE_LINE = re.compile(r"([A-Z]+):(?:\s+([A-Z]+(?:\s+[A-Z]+)*))?\s*$")


def read_test_repository(path):
    """Прочитать файл вида ``A: B C`` в словарь зависимостей."""
    graph = OrderedDict()
    errors = []
    try:
        with open(path, encoding="utf-8") as file:
            lines = list(file)
    except (OSError, UnicodeError) as error:
        raise ConfigError([f"не удалось прочитать репозиторий {path}: {error}"])
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = PACKAGE_LINE.fullmatch(stripped)
        if not match:
            errors.append(f"{path}, строка {number}: ожидался формат 'A: B C'")
            continue
        name, dependencies = match.groups()
        if name in graph:
            errors.append(f"{path}, строка {number}: повтор пакета {name}")
        graph[name] = dependencies.split() if dependencies else []
    if errors:
        raise ConfigError(errors)
    return graph


def filter_name(name):
    """Привести координаты или имя пакета к строке для фильтра."""
    return str(name)


def build_graph(root, dependencies, package_filter=""):
    """Построить упорядоченный граф рекурсивным DFS с защитой от циклов."""
    result = OrderedDict()
    visiting = set()

    def visit(package):
        """Рекурсивно посетить пакет и его неотфильтрованных потомков."""
        if package in result or package in visiting:
            return
        visiting.add(package)
        available = [item for item in dependencies(package)
                     if not package_filter
                     or package_filter not in filter_name(item)]
        result[package] = available
        for item in available:
            visit(item)
        visiting.remove(package)

    if package_filter and package_filter in filter_name(root):
        raise ConfigError([f"корневой пакет {root} исключён фильтром"])
    visit(root)
    return result


def repository_dependencies(repository):
    """Вернуть функцию зависимостей с диагностикой неизвестного пакета."""
    def dependencies(package):
        """Найти зависимости пакета тестового репозитория."""
        if package not in repository:
            raise ConfigError([f"пакет {package} отсутствует в репозитории"])
        return repository[package]
    return dependencies


def maven_dependencies(repository):
    """Вернуть функцию получения зависимостей Maven по координатам."""
    def dependencies(package):
        """Получить прямые зависимости одного Maven-пакета."""
        root, properties, managed = load_model(repository, package)
        section = child(root, "dependencies")
        if section is None:
            return []
        result = []
        for item in children(section, "dependency"):
            dependency = parse_dependency(item, properties, managed)
            if dependency is not None:
                result.append(dependency)
        return result
    return dependencies


def dependency_graph(config):
    """Построить граф из тестового файла или реального Maven."""
    if config.test_mode:
        repository = read_test_repository(config.repository_path)
        root = config.package
        dependencies = repository_dependencies(repository)
    else:
        coordinates = parse_coordinates(config.package)
        root = resolve_version(config.repository, coordinates)
        dependencies = maven_dependencies(config.repository)
    return build_graph(root, dependencies, config.package_filter)


def format_graph(graph):
    """Вывести каждую прямую связь графа и изолированные пакеты."""
    lines = []
    for package, dependencies in graph.items():
        if not dependencies:
            lines.append(str(package))
        for dependency in dependencies:
            lines.append(f"{package} -> {dependency}")
    return "\n".join(lines)
