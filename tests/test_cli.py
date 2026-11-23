"""Тесты командной строки этапа 2."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from depviz.cli import ERROR_PREFIX, EXIT_ERROR, EXIT_OK, main
from depviz.errors import ConfigError
from depviz.maven import Coordinates
from samples import build_rows

ARGPARSE_EXIT_CODE = 2
ROOT = Path(__file__).resolve().parent.parent


def test_success_prints_direct_dependencies(
        write_config, capsys, monkeypatch):
    """После загрузки конфигурации печатаются прямые зависимости."""
    dependencies = [Coordinates("g", "a", "1"), Coordinates("g", "b", "2")]
    monkeypatch.setattr("depviz.cli.direct_dependencies",
                        lambda config: dependencies)
    code = main(["-c", write_config(build_rows())])
    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert captured.out.splitlines() == ["g:a:1", "g:b:2"]
    assert captured.err == ""


def test_missing_default_config(tmp_path, monkeypatch, capsys):
    """Нет ``config.csv``: ошибка в stderr, код 1, stdout пуст."""
    monkeypatch.chdir(tmp_path)
    code = main([])
    captured = capsys.readouterr()
    assert code == EXIT_ERROR
    assert captured.out == ""
    assert captured.err == (
        f"{ERROR_PREFIX}файл конфигурации не найден: config.csv\n")


def test_dependency_error(write_config, capsys, monkeypatch):
    """Ошибка сети сообщается отдельно и даёт код 1."""
    def fail(config):
        raise ConfigError(["репозиторий недоступен"])

    monkeypatch.setattr("depviz.cli.direct_dependencies", fail)
    code = main(["-c", write_config(build_rows())])
    assert code == EXIT_ERROR
    assert "репозиторий недоступен" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--unknown"], ["-c"], ["extra"]])
def test_argparse_errors_exit_with_code_two(argv, capsys):
    """Ошибки аргументов: argparse завершает работу с кодом 2."""
    with pytest.raises(SystemExit) as info:
        main(argv)
    assert info.value.code == ARGPARSE_EXIT_CODE
    assert "usage: depviz" in capsys.readouterr().err


def run_module(args, cwd):
    """Запустить ``python -m depviz`` как отдельный процесс."""
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    return subprocess.run([sys.executable, "-m", "depviz", *args],
                          cwd=str(cwd), env=env, capture_output=True,
                          text=True, encoding="utf-8")


def test_module_entry_point_error(tmp_path):
    """``python -m depviz`` с ошибкой завершается с кодом 1."""
    result = run_module(["-c", "missing.csv"], tmp_path)
    assert result.returncode == EXIT_ERROR
    assert result.stdout == ""
    assert "файл конфигурации не найден: missing.csv" in result.stderr
