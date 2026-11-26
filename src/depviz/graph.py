"""Тестовый репозиторий и рекурсивный DFS графа зависимостей."""

import re
from collections import OrderedDict
from dataclasses import replace

from depviz.errors import ConfigError
from depviz.maven import (load_effective_model, parse_coordinates,
                          resolve_version)

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


class MavenGraphBuilder:
    """Рекурсивный DFS с Maven nearest-wins и наследованием exclusions."""

    def __init__(self, repository, package_filter):
        """Создать пустые кэши и состояние обхода."""
        self.repository = repository
        self.package_filter = package_filter
        self.root = None
        self.managed = {}
        self.model_cache = {}
        self.dependency_cache = {}
        self.selected = {}
        self.depths = {}
        self.result = OrderedDict()
        self.emitted = set()

    def direct(self, package):
        """Получить зависимости и передать им накопленные exclusions."""
        key = str(package)
        if key not in self.dependency_cache:
            model = load_effective_model(self.repository, package,
                                         self.model_cache)
            self.dependency_cache[key] = model.dependencies
        result = []
        for dependency in self.dependency_cache[key]:
            if package.key != self.root.key and dependency.optional:
                continue
            if any(item.matches(dependency) for item in package.exclusions):
                continue
            exclusions = package.exclusions + tuple(
                item for item in dependency.exclusions
                if item not in package.exclusions
            )
            version = self.managed.get(":".join(dependency.key),
                                       dependency.version)
            result.append(replace(dependency, version=version,
                                  exclusions=exclusions))
        return result

    def allowed(self, package):
        """Проверить пользовательский фильтр координат."""
        return (not self.package_filter
                or self.package_filter not in filter_name(package))

    def select(self, package, depth):
        """Выбрать первую ближайшую версию каждого groupId:artifactId."""
        key = package.key
        if key in self.depths and self.depths[key] <= depth:
            return
        self.selected[key] = package
        self.depths[key] = depth
        for dependency in self.direct(package):
            if self.allowed(dependency):
                self.select(dependency, depth + 1)

    def emit(self, package):
        """Вывести выбранные узлы в порядке рекурсивного DFS."""
        if package.key in self.emitted:
            return
        self.emitted.add(package.key)
        dependencies = []
        seen = set()
        for dependency in self.direct(package):
            if dependency.key in self.selected and dependency.key not in seen:
                seen.add(dependency.key)
                dependencies.append(self.selected[dependency.key])
        self.result[package] = dependencies
        for dependency in dependencies:
            self.emit(dependency)

    def build(self, root):
        """Сначала выбрать версии, затем построить достижимый граф."""
        self.root = root
        model = load_effective_model(self.repository, root, self.model_cache)
        self.managed = model.managed
        self.select(root, 0)
        self.emit(root)
        return self.result


def build_maven_graph(repository, root, package_filter=""):
    """Построить Maven-граф рекурсивным DFS с nearest-wins mediation."""
    if package_filter and package_filter in filter_name(root):
        raise ConfigError([f"корневой пакет {root} исключён фильтром"])
    return MavenGraphBuilder(repository, package_filter).build(root)


def dependency_graph(config, reverse=False):
    """Построить граф прямых или обратных зависимостей."""
    if not config.test_mode:
        if reverse:
            raise ConfigError([
                "обратный поиск Maven доступен в тестовом режиме"
            ])
        coordinates = parse_coordinates(config.package)
        root = resolve_version(config.repository, coordinates)
        return build_maven_graph(config.repository, root,
                                 config.package_filter)
    repository = read_test_repository(config.repository_path)
    if reverse:
        repository = invert_repository(repository)
    dependencies = repository_dependencies(repository)
    return build_graph(config.package, dependencies, config.package_filter)


def invert_repository(repository):
    """Развернуть все связи полного тестового репозитория."""
    inverted = OrderedDict((package, []) for package in repository)
    for package, dependencies in repository.items():
        for dependency in dependencies:
            if dependency not in inverted:
                raise ConfigError([
                    f"пакет {dependency} отсутствует в репозитории"
                ])
            inverted[dependency].append(package)
    return inverted


def format_graph(graph):
    """Вывести каждую прямую связь графа и изолированные пакеты."""
    lines = []
    for package, dependencies in graph.items():
        if not dependencies:
            lines.append(str(package))
        for dependency in dependencies:
            lines.append(f"{package} -> {dependency}")
    return "\n".join(lines)
