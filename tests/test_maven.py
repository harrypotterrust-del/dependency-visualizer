"""Тесты разбора Maven POM и адресов репозитория."""

from depviz.maven import (Coordinates, parse_coordinates, parse_pom,
                          pom_url)

POM = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <groupId>example</groupId><artifactId>app</artifactId>
  <version>1.0</version>
  <properties><lib.version>2.5</lib.version></properties>
  <dependencies>
    <dependency>
      <groupId>org.example</groupId><artifactId>core</artifactId>
      <version>${lib.version}</version>
    </dependency>
    <dependency>
      <groupId>org.example</groupId><artifactId>tests</artifactId>
      <version>1</version><scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.example</groupId><artifactId>optional</artifactId>
      <version>1</version><optional>true</optional>
    </dependency>
  </dependencies>
</project>
"""


def test_pom_url():
    """Точки groupId заменяются элементами пути репозитория."""
    coordinates = Coordinates("org.example", "demo", "1.2")
    assert pom_url("https://repo.example/maven2/", coordinates) == (
        "https://repo.example/maven2/org/example/demo/1.2/demo-1.2.pom")


def test_default_version_is_latest():
    """Отсутствующая версия обозначается маркером LATEST."""
    assert parse_coordinates("g:a").version == "LATEST"


def test_parse_direct_dependencies_with_namespace_and_properties():
    """Учитываются property и namespace, test/optional пропускаются."""
    assert parse_pom(POM) == [Coordinates("org.example", "core", "2.5")]


def test_empty_dependencies():
    """POM без зависимостей даёт пустой список."""
    assert parse_pom("<project><dependencies/></project>") == []
