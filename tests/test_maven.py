"""Тесты разбора Maven POM и адресов репозитория."""

import pytest

from depviz.errors import ConfigError
from depviz.maven import (Coordinates, load_effective_model,
                          parse_coordinates, parse_pom, pom_url)

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
    """Property работают, test пропускается, optional сохраняется."""
    assert parse_pom(POM) == [
        Coordinates("org.example", "core", "2.5"),
        Coordinates("org.example", "optional", "1", optional=True),
    ]


def test_empty_dependencies():
    """POM без зависимостей даёт пустой список."""
    assert parse_pom("<project><dependencies/></project>") == []


def test_effective_model_inherits_parent_and_properties(monkeypatch):
    """Parent даёт координаты, properties и наследуемые зависимости."""
    parent = """<project><groupId>g</groupId><artifactId>parent</artifactId>
      <version>1</version><properties><lib.version>1</lib.version></properties>
      <dependencies><dependency><groupId>g</groupId>
      <artifactId>inherited</artifactId><version>${project.version}</version>
      </dependency></dependencies></project>"""
    app = """<project><parent><groupId>g</groupId>
      <artifactId>parent</artifactId><version>1</version></parent>
      <artifactId>app</artifactId><version>2</version>
      <properties><lib.version>2</lib.version></properties><dependencies>
      <dependency><groupId>g</groupId><artifactId>direct</artifactId>
      <version>${lib.version}</version></dependency></dependencies></project>"""
    monkeypatch.setattr("depviz.maven.download",
                        lambda url: parent if "parent" in url else app)
    model = load_effective_model("https://repo", Coordinates("g", "app", "2"))
    assert model.dependencies == [Coordinates("g", "inherited", "2"),
                                  Coordinates("g", "direct", "2")]


def test_effective_model_imports_bom(monkeypatch):
    """BOM import предоставляет версию прямой зависимости."""
    bom = """<project><groupId>g</groupId><artifactId>bom</artifactId>
      <version>1</version><dependencyManagement><dependencies><dependency>
      <groupId>g</groupId><artifactId>lib</artifactId><version>3</version>
      </dependency></dependencies></dependencyManagement></project>"""
    app = """<project><groupId>g</groupId><artifactId>app</artifactId>
      <version>1</version><dependencyManagement><dependencies><dependency>
      <groupId>g</groupId><artifactId>bom</artifactId><version>1</version>
      <type>pom</type><scope>import</scope></dependency></dependencies>
      </dependencyManagement><dependencies><dependency><groupId>g</groupId>
      <artifactId>lib</artifactId></dependency></dependencies></project>"""
    monkeypatch.setattr("depviz.maven.download",
                        lambda url: bom if "/bom/" in url else app)
    model = load_effective_model("https://repo", Coordinates("g", "app", "1"))
    assert model.dependencies == [Coordinates("g", "lib", "3")]


def test_missing_dependency_version_is_an_error():
    """Зависимость без версии не исчезает молча из графа."""
    pom = """<project><dependencies><dependency><groupId>g</groupId>
      <artifactId>lib</artifactId></dependency></dependencies></project>"""
    with pytest.raises(ConfigError, match="не указана версия"):
        parse_pom(pom)
