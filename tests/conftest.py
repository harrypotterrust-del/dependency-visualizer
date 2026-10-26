"""Общие фикстуры тестов: временные файлы конфигурации и репозитория."""

from pathlib import Path
from typing import Callable, List

import pytest

from samples import REPO_TEXT


@pytest.fixture
def write_config(tmp_path: Path) -> Callable[..., str]:
    """Вернуть функцию, создающую файл конфигурации во временной папке."""
    def writer(rows: List[str], name: str = "config.csv") -> str:
        """Записать строки ``rows`` в файл ``name`` и вернуть его путь."""
        path = tmp_path / name
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return str(path)

    return writer


@pytest.fixture
def repo_file(tmp_path: Path) -> str:
    """Создать небольшой файл тестового репозитория и вернуть путь."""
    path = tmp_path / "repo.txt"
    path.write_text(REPO_TEXT, encoding="utf-8")
    return str(path)
