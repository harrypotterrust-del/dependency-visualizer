"""Представление графа в PlantUML и получение SVG-изображения."""

import hashlib
import zlib
from pathlib import Path

from depviz.maven import download

PLANTUML_SERVER = "https://www.plantuml.com/plantuml/svg/"
ALPHABET = ("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "abcdefghijklmnopqrstuvwxyz-_")


def plantuml_text(graph):
    """Сформировать диаграмму со стабильными идентификаторами узлов."""
    aliases = {
        package: "N" + hashlib.sha1(
            str(package).encode("utf-8")
        ).hexdigest()[:12]
        for package in graph
    }
    lines = ["@startuml", "left to right direction",
             "skinparam monochrome true"]
    for package, alias in aliases.items():
        label = str(package).replace('"', "'")
        lines.append(f'rectangle "{label}" as {alias}')
    for package, dependencies in graph.items():
        for dependency in dependencies:
            lines.append(f"{aliases[package]} --> {aliases[dependency]}")
    lines.append("@enduml")
    return "\n".join(lines)


def encode6bit(value):
    """Закодировать шесть бит алфавитом PlantUML."""
    return ALPHABET[value & 0x3F]


def append3bytes(first, second, third):
    """Закодировать три байта в четыре символа PlantUML."""
    combined = (first << 16) | (second << 8) | third
    return "".join(encode6bit(combined >> shift)
                   for shift in (18, 12, 6, 0))


def plantuml_encode(text):
    """Выполнить deflate и специфическое base64-кодирование PlantUML."""
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    data = compressor.compress(text.encode("utf-8"))
    data += compressor.flush()
    result = []
    for offset in range(0, len(data), 3):
        chunk = data[offset:offset + 3]
        chunk = chunk.ljust(3, b"\0")
        result.append(append3bytes(*chunk))
    return "".join(result)


def render_svg(graph, output_path):
    """Получить SVG с PlantUML-сервера и сохранить в указанный файл."""
    source = plantuml_text(graph)
    url = PLANTUML_SERVER + plantuml_encode(source)
    svg = download(url)
    if "<svg" not in svg:
        raise ValueError("PlantUML-сервер вернул не SVG")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")
    return source, path
