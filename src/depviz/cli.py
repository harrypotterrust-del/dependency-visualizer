"""Интерфейс командной строки анализа и визуализации зависимостей."""

import argparse
import sys
import webbrowser
from typing import List, Optional

from depviz.config import DEFAULT_CONFIG, load_config
from depviz.errors import ConfigError
from depviz.graph import dependency_graph, format_graph
from depviz.plantuml import plantuml_text, render_svg

EXIT_OK = 0
EXIT_ERROR = 1
ERROR_PREFIX = "ошибка: "


def build_parser() -> argparse.ArgumentParser:
    """Создать разборщик аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="depviz",
        description="Визуализатор графа зависимостей Maven "
                    "(этап 5: PlantUML).",
    )
    parser.add_argument("-c", "--config", metavar="PATH",
                        default=DEFAULT_CONFIG,
                        help="путь к CSV-файлу конфигурации "
                             "(по умолчанию: %(default)s)")
    parser.add_argument("--reverse", action="store_true",
                        help="вывести пакеты, зависящие от заданного")
    parser.add_argument("--plantuml", action="store_true",
                        help="дополнительно вывести текст PlantUML")
    parser.add_argument("--visualize", nargs="?", metavar="SVG",
                        const="build/dependencies.svg",
                        help="сохранить SVG и открыть его в браузере")
    return parser


def report_errors(error: ConfigError) -> None:
    """Вывести каждое сообщение ошибки отдельной строкой в stderr."""
    for message in error.messages:
        print(f"{ERROR_PREFIX}{message}", file=sys.stderr)


def visualize(graph, output_path):
    """Сохранить изображение и открыть его штатным браузером."""
    source, path = render_svg(graph, output_path)
    print(source)
    print(f"Изображение сохранено: {path}")
    webbrowser.open(path.resolve().as_uri())


def main(argv: Optional[List[str]] = None) -> int:
    """Запустить анализ и вернуть код завершения."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        graph = dependency_graph(config, reverse=args.reverse)
        print(format_graph(graph))
        if args.plantuml and not args.visualize:
            print(plantuml_text(graph))
        if args.visualize:
            visualize(graph, args.visualize)
    except (ConfigError, OSError, ValueError) as error:
        if isinstance(error, ConfigError):
            report_errors(error)
        else:
            print(f"{ERROR_PREFIX}{error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK
