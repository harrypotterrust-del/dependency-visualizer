"""Интерфейс командной строки: разбор аргументов и вывод параметров."""

import argparse
import sys
from typing import List, Optional

from depviz.config import DEFAULT_CONFIG, load_config
from depviz.errors import ConfigError
from depviz.graph import dependency_graph, format_graph

EXIT_OK = 0
EXIT_ERROR = 1
ERROR_PREFIX = "ошибка: "


def build_parser() -> argparse.ArgumentParser:
    """Создать разборщик аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="depviz",
        description="Визуализатор графа зависимостей Maven "
                    "(этап 3: рекурсивный DFS).",
    )
    parser.add_argument("-c", "--config", metavar="PATH",
                        default=DEFAULT_CONFIG,
                        help="путь к CSV-файлу конфигурации "
                             "(по умолчанию: %(default)s)")
    return parser


def report_errors(error: ConfigError) -> None:
    """Вывести каждое сообщение ошибки отдельной строкой в stderr."""
    for message in error.messages:
        print(f"{ERROR_PREFIX}{message}", file=sys.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    """Запустить программу и вернуть код завершения.

    ``argv`` - аргументы без имени программы; по умолчанию берутся
    настоящие аргументы процесса. При успехе параметры печатаются
    в stdout (код 0), при ошибке конфигурации сообщения идут в stderr
    (код 1). Ошибки самих аргументов argparse завершает с кодом 2.
    """
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        report_errors(error)
        return EXIT_ERROR
    try:
        graph = dependency_graph(config)
    except ConfigError as error:
        report_errors(error)
        return EXIT_ERROR
    print(format_graph(graph))
    return EXIT_OK
