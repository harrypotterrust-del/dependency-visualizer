"""Получение прямых зависимостей из Maven POM стандартными средствами."""

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from depviz.errors import ConfigError

HTTP_TIMEOUT = 20
DEFAULT_VERSION = "LATEST"


@dataclass(frozen=True)
class Coordinates:
    """Координаты артефакта Maven."""

    group: str
    artifact: str
    version: str

    def __str__(self):
        """Вернуть привычную запись group:artifact:version."""
        return f"{self.group}:{self.artifact}:{self.version}"


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
    return [item for item in element if local_name(item.tag) == name]


def child(element, name):
    """Найти первого непосредственного потомка."""
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


def parse_pom(text):
    """Извлечь координаты прямых compile/runtime зависимостей из POM."""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        raise ConfigError([f"некорректный POM XML: {error}"])
    properties = read_properties(root)
    dependencies = child(root, "dependencies")
    if dependencies is None:
        return []
    result = []
    for item in children(dependencies, "dependency"):
        dependency = parse_dependency(item, properties)
        if dependency is not None:
            result.append(dependency)
    return result


def read_properties(root):
    """Прочитать properties и основные координаты для подстановок."""
    properties = {
        "project.groupId": child_text(root, "groupId"),
        "project.artifactId": child_text(root, "artifactId"),
        "project.version": child_text(root, "version"),
    }
    section = child(root, "properties")
    if section is not None:
        for item in section:
            if item.text:
                properties[local_name(item.tag)] = item.text.strip()
    return properties


def substitute(value, properties):
    """Подставить простые Maven-переменные вида ${name}."""
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


def parse_dependency(element, properties, managed=None):
    """Разобрать dependency, пропустив optional/test/provided/system."""
    scope = child_text(element, "scope", "compile")
    optional = child_text(element, "optional", "false")
    if scope not in ("compile", "runtime") or optional == "true":
        return None
    values = [child_text(element, name) for name in
              ("groupId", "artifactId", "version")]
    values = [substitute(value, properties) for value in values]
    managed = managed or {}
    if not values[2]:
        values[2] = managed.get(":".join(values[:2]), "")
    if not all(values) or any("${" in value for value in values):
        return None
    return Coordinates(*values)


def managed_dependencies(root, properties):
    """Прочитать версии из dependencyManagement текущего POM."""
    management = child(root, "dependencyManagement")
    dependencies = child(management, "dependencies") if management else None
    result = {}
    if dependencies is not None:
        for item in children(dependencies, "dependency"):
            values = [child_text(item, name) for name in
                      ("groupId", "artifactId", "version")]
            values = [substitute(value, properties) for value in values]
            if all(values):
                result[":".join(values[:2])] = values[2]
    return result


def parent_coordinates(root, properties):
    """Получить координаты родителя, если он указан."""
    parent = child(root, "parent")
    if parent is None:
        return None
    values = [child_text(parent, name) for name in
              ("groupId", "artifactId", "version")]
    values = [substitute(value, properties) for value in values]
    return Coordinates(*values) if all(values) else None


def metadata_url(repository, coordinates):
    """Сформировать URL метаданных для выбора последней версии."""
    group_path = coordinates.group.replace(".", "/")
    return "/".join((repository.rstrip("/"), group_path,
                     coordinates.artifact, "maven-metadata.xml"))


def resolve_version(repository, coordinates):
    """Разрешить отсутствующую версию через maven-metadata.xml."""
    if coordinates.version != DEFAULT_VERSION:
        return coordinates
    root = ElementTree.fromstring(download(metadata_url(repository,
                                                        coordinates)))
    versioning = child(root, "versioning")
    version = child_text(versioning, "release")
    version = version or child_text(versioning, "latest")
    if not version:
        raise ConfigError([f"не найдена последняя версия {coordinates}"])
    return Coordinates(coordinates.group, coordinates.artifact, version)


def load_model(repository, coordinates):
    """Загрузить POM и объединить свойства и версии его родителей."""
    roots = []
    current = coordinates
    while current is not None:
        url = pom_url(repository, current)
        root = ElementTree.fromstring(download(url))
        roots.append(root)
        current = parent_coordinates(root, read_properties(root))
    properties = {}
    managed = {}
    for root in reversed(roots):
        properties.update(read_properties(root))
        managed.update(managed_dependencies(root, properties))
    return roots[0], properties, managed


def direct_dependencies(config):
    """Загрузить POM корневого пакета и вернуть прямые зависимости."""
    coordinates = parse_coordinates(config.package)
    coordinates = resolve_version(config.repository, coordinates)
    root, properties, managed = load_model(config.repository, coordinates)
    section = child(root, "dependencies")
    if section is None:
        return []
    result = []
    for item in children(section, "dependency"):
        dependency = parse_dependency(item, properties, managed)
        if dependency is not None:
            result.append(dependency)
    return result
