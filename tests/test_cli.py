"""Тесты командной строки: коды завершения, stdout и stderr."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from depviz.cli import ERROR_PREFIX, EXIT_ERROR, EXIT_OK, main
from samples import MAVEN_PACKAGE, MAVEN_REPOSITORY, build_rows

ARGPARSE_EXIT_CODE = 2
ROOT = Path(__file__).resolve().parent.parent
EXPECTED_LINES = [
    f"package={MAVEN_PACKAGE}",
    f"repository={MAVEN_REPOSITORY}",
    "test_mode=false",
    "filter=junit",
]


def test_success_prints_parameters(write_config, capsys):
    """Успех: четыре строки ``ключ=значение`` в stdout, код 0."""
    code = main(["-c", write_config(build_rows())])
    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert captured.out.splitlines() == EXPECTED_LINES
    assert captured.err == ""


def test_long_option_name(write_config, capsys):
    """Длинное имя ``--config`` работает так же, как ``-c``."""
    code = main(["--config", write_config(build_rows())])
    assert code == EXIT_OK
    assert capsys.readouterr().out.splitlines() == EXPECTED_LINES


def test_default_config_is_read_from_current_dir(
        write_config, tmp_path, monkeypatch, capsys):
    """Без аргументов читается ``config.csv`` из текущей папки."""
    write_config(build_rows())
    monkeypatch.chdir(tmp_path)
    assert main([]) == EXIT_OK
    assert capsys.readouterr().out.splitlines() == EXPECTED_LINES


def test_missing_default_config(tmp_path, monkeypatch, capsys):
    """Нет ``config.csv``: ошибка в stderr, код 1, stdout пуст."""
    monkeypatch.chdir(tmp_path)
    code = main([])
    captured = capsys.readouterr()
    assert code == EXIT_ERROR
    assert captured.out == ""
    assert captured.err == (
        f"{ERROR_PREFIX}файл конфигурации не найден: config.csv\n")


def test_errors_go_to_stderr_one_per_line(write_config, capsys):
    """Каждая ошибка - отдельная строка stderr с префиксом."""
    path = write_config(["key,value", "package,", "test_mode,maybe"])
    code = main(["-c", path])
    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert code == EXIT_ERROR
    assert captured.out == ""
    assert all(line.startswith(ERROR_PREFIX) for line in lines)
    assert any("пустое значение" in line for line in lines)
    assert any("не задан обязательный параметр «repository»" in line
               for line in lines)
    assert any("параметр «test_mode»" in line for line in lines)


def test_file_error_exit_code(tmp_path, capsys):
    """Каталог вместо файла конфигурации: код 1 и понятное сообщение."""
    code = main(["-c", str(tmp_path)])
    assert code == EXIT_ERROR
    assert "это каталог" in capsys.readouterr().err


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


def test_module_entry_point_success(write_config, tmp_path):
    """``python -m depviz`` печатает параметры и завершается с кодом 0."""
    result = run_module(["-c", write_config(build_rows())], tmp_path)
    assert result.returncode == EXIT_OK
    assert result.stdout.splitlines() == EXPECTED_LINES


def test_module_entry_point_error(tmp_path):
    """``python -m depviz`` с ошибкой завершается с кодом 1."""
    result = run_module(["-c", "missing.csv"], tmp_path)
    assert result.returncode == EXIT_ERROR
    assert result.stdout == ""
    assert "файл конфигурации не найден: missing.csv" in result.stderr
