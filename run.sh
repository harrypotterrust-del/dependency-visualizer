#!/bin/sh
# Запуск программы: ./run.sh [-c PATH]
# Без аргументов читается config.csv из текущей папки.
# Интерпретатор можно заменить: PYTHON=.venv/bin/python ./run.sh
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHONPATH="$ROOT/src" exec "${PYTHON:-python3}" -m depviz "$@"
