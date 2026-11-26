"""Получение зависимостей из Maven POM стандартными средствами."""

from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from depviz.errors import ConfigError

HTTP_TIMEOUT = 20
DEFAULT_VERSION = "LATEST"


@dataclass(frozen=True)
class Exclusion:
    """Исключение транзитивной зависимости Maven."""

    group: str
    artifact: str

    def matches(self, coordinates):
        """Проверить координаты с учётом Maven wildcard."""
        return (self.group in ("*", coordinates.group)
                and self.artifact in ("*", coordinates.artifact))


@dataclass(frozen=True)
class Coordinates:
    """Координаты артефакта Maven и накопленные исключения."""

    group: str
    artifact: str
    version: str
    exclusions: Tuple[Exclusion, ...] = ()
    optional: bool = False

    @property
    def key(self):
        """Вернуть идентификатор артефакта без версии."""
        return self.group, self.artifact

    def __str__(self):
        """Вернуть привычную запись group:artifact:version."""
        return f"{self.group}:{self.artifact}:{self.version}"


@dataclass
class EffectiveModel:
    """Свойства, управление версиями и зависимости effective POM."""

    root: ElementTree.Element
    properties: Dict[str, str]
    managed: Dict[str, str]
    dependencies: list


def parse_coordinates(value):
    """Разобрать две или три части координат из конфигурации."""
    parts = value.split(":")
    version = parts[2] if len(parts) == 3 else DEFAULT_VERSION
    return Coordinates(parts[0], parts[1], version)


def local_name(tag):
    """Убрать XML namespace из имени элемента."""
    return tag.rsplit("}", 1)[-1]


def children(element, name):
    """Найти непосредственных потомков по имени без namespace."""
    if element is None:
        return []
    return [item for item in element if local_name(item.tag) == name]


def child(element, name):
    """Найти первого непосредственного потомка."""
    if element is None:
        return None
    matches = children(element, name)
    return matches[0] if matches else None


def child_text(element, name, default=""):
    """Прочитать текст непосредственного потомка."""
    item = child(element, name)
    return item.text.strip() if item is not None and item.text else default


def pom_url(repository, coordinates):
    """Сформировать URL POM-файла в стандартной раскладке Maven."""
    group_path = coordinates.group.replace(".", "/")
    name = f"{coordinates.artifact}-{coordinates.version}.pom"
    parts = (repository.rstrip("/"), group_path, coordinates.artifact,
             coordinates.version, name)
    return "/".join(parts)


def download(url):
    """Скачать текстовый ресурс с понятной диагностикой HTTP и сети."""
    request = Request(url, headers={"User-Agent": "depviz/1.0"})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return response.read().decode("utf-8")
    except HTTPError as error:
        raise ConfigError([f"не удалось получить {url}: HTTP {error.code}"])
    except (URLError, OSError, UnicodeError) as error:
        reason = getattr(error, "reason", error)
        raise ConfigError([f"не удалось получить {url}: {reason}"])


def parse_xml(text, description="POM"):
    """Разобрать XML и превратить ошибку синтаксиса в ConfigError."""
    try:
        return ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        raise ConfigError([f"некорректный {description} XML: {error}"])


def read_custom_properties(root):
    """Прочитать только секцию properties POM."""
    properties = {}
    section = child(root, "properties")
    if section is not None:
        for item in section:
            if item.text:
                properties[local_name(item.tag)] = item.text.strip()
    return properties


def read_properties(root):
    """Прочитать properties и основные координаты для подстановок."""
    properties = {
        "project.groupId": child_text(root, "groupId"),
        "project.artifactId": child_text(root, "artifactId"),
        "project.version": child_text(root, "version"),
    }
    properties.update(read_custom_properties(root))
    return properties


def substitute(value, properties):
    """Подставить Maven-переменные вида ${name}."""
    result = value
    for _ in range(len(properties) + 1):
        changed = False
        for key, replacement in properties.items():
            marker = "${" + key + "}"
            if marker in result:
                result = result.replace(marker, replacement)
                changed = True
        if not changed:
            break
    return result


def read_exclusions(element):
    """Прочитать исключения транзитивных зависимостей."""
    result = []
    section = child(element, "exclusions")
    for item in children(section, "exclusion"):
        group = child_text(item, "groupId", "*")
        artifact = child_text(item, "artifactId", "*")
        result.append(Exclusion(group, artifact))
    return tuple(result)


def unresolved(value):
    """Проверить, осталась ли в значении неразрешённая переменная."""
    return not value or "${" in value


def parse_dependency(element, properties, managed=None):
    """Разобрать compile/runtime dependency, optional и exclusions."""
    scope = substitute(child_text(element, "scope", "compile"), properties)
    optional = substitute(child_text(element, "optional", "false"),
                          properties).lower()
    if scope not in ("compile", "runtime"):
        return None
    values = [substitute(child_text(element, name), properties)
              for name in ("groupId", "artifactId", "version")]
    managed = managed or {}
    if not values[2]:
        values[2] = managed.get(":".join(values[:2]), "")
    if any(unresolved(value) for value in values[:2]):
        raise ConfigError([
            "не удалось разрешить координаты зависимости: "
            + ":".join(values)
        ])
    if unresolved(values[2]):
        raise ConfigError([
            f"не указана версия зависимости {values[0]}:{values[1]}"
        ])
    return Coordinates(*values, exclusions=read_exclusions(element),
                       optional=optional == "true")


def managed_dependencies(root, properties):
    """Прочитать неимпортированные версии dependencyManagement."""
    management = child(root, "dependencyManagement")
    dependencies = child(management, "dependencies")
    result = {}
    imports = []
    for item in children(dependencies, "dependency"):
        values = [substitute(child_text(item, name), properties)
                  for name in ("groupId", "artifactId", "version")]
        scope = substitute(child_text(item, "scope"), properties)
        packaging = substitute(child_text(item, "type", "jar"), properties)
        if scope == "import" and packaging == "pom":
            if any(unresolved(value) for value in values):
                raise ConfigError([
                    "не удалось разрешить координаты импортированного BOM: "
                    + ":".join(values)
                ])
            imports.append(Coordinates(*values))
        elif all(not unresolved(value) for value in values):
            result[":".join(values[:2])] = values[2]
    return result, imports


def parent_coordinates(root, properties=None):
    """Получить координаты родителя, если он указан."""
    parent = child(root, "parent")
    if parent is None:
        return None
    properties = properties or read_properties(root)
    values = [substitute(child_text(parent, name), properties)
              for name in ("groupId", "artifactId", "version")]
    if any(unresolved(value) for value in values):
        raise ConfigError(["не удалось разрешить координаты parent POM"])
    return Coordinates(*values)


def metadata_url(repository, coordinates):
    """Сформировать URL метаданных для выбора последней версии."""
    group_path = coordinates.group.replace(".", "/")
    return "/".join((repository.rstrip("/"), group_path,
                     coordinates.artifact, "maven-metadata.xml"))


def resolve_version(repository, coordinates):
    """Разрешить отсутствующую версию через maven-metadata.xml."""
    if coordinates.version != DEFAULT_VERSION:
        return coordinates
    root = parse_xml(download(metadata_url(repository, coordinates)),
                     "maven-metadata")
    versioning = child(root, "versioning")
    version = child_text(versioning, "release")
    version = version or child_text(versioning, "latest")
    if not version:
        raise ConfigError([f"не найдена последняя версия {coordinates}"])
    return Coordinates(coordinates.group, coordinates.artifact, version)


def model_properties(roots):
    """Объединить свойства родителей и унаследованные координаты проекта."""
    properties = {}
    for root in reversed(roots):
        properties.update(read_custom_properties(root))
        parent = child(root, "parent")
        group = child_text(root, "groupId") or child_text(parent, "groupId")
        version = child_text(root, "version") or child_text(parent, "version")
        artifact = child_text(root, "artifactId")
        parent_group = child_text(parent, "groupId")
        parent_version = child_text(parent, "version")
        values = {
            "project.groupId": group,
            "pom.groupId": group,
            "groupId": group,
            "project.artifactId": artifact,
            "pom.artifactId": artifact,
            "artifactId": artifact,
            "project.version": version,
            "pom.version": version,
            "version": version,
            "project.parent.groupId": parent_group,
            "project.parent.version": parent_version,
        }
        properties.update({key: value for key, value in values.items()
                           if value})
        for key, value in list(properties.items()):
            properties[key] = substitute(value, properties)
    return properties


def load_parent_chain(repository, coordinates):
    """Загрузить цепочку POM от анализируемого пакета к предкам."""
    roots = []
    current = coordinates
    while current is not None:
        if current.key + (current.version,) in [
                item.key + (item.version,) for item, _ in roots]:
            raise ConfigError([f"цикл parent POM у {current}"])
        root = parse_xml(download(pom_url(repository, current)))
        roots.append((current, root))
        current = parent_coordinates(root)
    return roots


def effective_management(repository, roots, properties, cache, loading):
    """Объединить dependencyManagement предков и импортированные BOM."""
    managed = {}
    for _, root in reversed(roots):
        own, imports = managed_dependencies(root, properties)
        for bom in imports:
            model = load_effective_model(repository, bom, cache, loading)
            managed.update(model.managed)
        managed.update(own)
    return managed


def effective_dependencies(roots, properties, managed):
    """Унаследовать зависимости, заменяя родительские версии дочерними."""
    dependencies = OrderedDict()
    for _, root in reversed(roots):
        section = child(root, "dependencies")
        for item in children(section, "dependency"):
            dependency = parse_dependency(item, properties, managed)
            if dependency is not None:
                dependencies[dependency.key] = dependency
    return list(dependencies.values())


def load_effective_model(repository, coordinates, cache=None, loading=None):
    """Загрузить effective POM с родителями, BOM и зависимостями."""
    cache = cache if cache is not None else {}
    loading = loading if loading is not None else set()
    cache_key = (repository, str(coordinates))
    if cache_key in cache:
        return cache[cache_key]
    if cache_key in loading:
        raise ConfigError([f"цикл parent/BOM POM у {coordinates}"])
    loading.add(cache_key)
    try:
        roots = load_parent_chain(repository, coordinates)
        properties = model_properties([root for _, root in roots])
        managed = effective_management(repository, roots, properties,
                                       cache, loading)
        dependencies = effective_dependencies(roots, properties, managed)
        model = EffectiveModel(roots[0][1], properties, managed, dependencies)
        cache[cache_key] = model
        return model
    finally:
        loading.remove(cache_key)


def load_model(repository, coordinates):
    """Загрузить POM и объединить свойства и версии его родителей."""
    model = load_effective_model(repository, coordinates)
    return model.root, model.properties, model.managed


def direct_dependencies(config):
    """Загрузить POM корневого пакета и вернуть прямые зависимости."""
    coordinates = parse_coordinates(config.package)
    coordinates = resolve_version(config.repository, coordinates)
    return load_effective_model(config.repository, coordinates).dependencies


def parse_pom(text):
    """Извлечь координаты прямых compile/runtime зависимостей из POM."""
    root = parse_xml(text)
    properties = read_properties(root)
    managed, _ = managed_dependencies(root, properties)
    dependencies = child(root, "dependencies")
    result = []
    for item in children(dependencies, "dependency"):
        dependency = parse_dependency(item, properties, managed)
        if dependency is not None:
            result.append(dependency)
    return result
