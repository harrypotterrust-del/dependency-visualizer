"""Тесты готовых примеров: configs/ и repos/ должны соответствовать коду."""

from pathlib import Path

import pytest

from depviz.config import load_config
from depviz.errors import ConfigError

ROOT = Path(__file__).resolve().parent.parent
GOOD_CONFIGS = sorted((ROOT / "configs").glob("*.csv")) + [
    ROOT / "config.csv"]
ERROR_CONFIGS = sorted((ROOT / "configs" / "errors").glob("*.csv"))


def test_examples_are_present():
    """Папки с примерами не пусты."""
    assert GOOD_CONFIGS
    assert ERROR_CONFIGS


@pytest.mark.parametrize("path", GOOD_CONFIGS, ids=lambda p: p.name)
def test_good_example_loads(path):
    """Каждый пример из configs/ загружается без ошибок."""
    config = load_config(str(path))
    assert config.package


@pytest.mark.parametrize("path", ERROR_CONFIGS, ids=lambda p: p.name)
def test_error_example_fails(path):
    """Каждый пример из configs/errors/ даёт хотя бы одну ошибку."""
    with pytest.raises(ConfigError) as info:
        load_config(str(path))
    assert info.value.messages
    assert all(str(path) in message for message in info.value.messages)


def test_test_repository_lines_have_expected_format():
    """Строки repos/simple.txt имеют вид ``A: B C`` с заглавными буквами."""
    text = (ROOT / "repos" / "simple.txt").read_text(encoding="utf-8")
    for line in text.splitlines():
        name, _, deps = line.partition(":")
        assert name.isalpha() and name.isupper()
        assert all(dep.isalpha() and dep.isupper() for dep in deps.split())
