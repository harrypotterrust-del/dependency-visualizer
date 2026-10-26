"""Образцы данных для тестов: строки CSV с допустимыми значениями."""

from typing import Dict, List, Optional

HEADER_ROW = "key,value"
MAVEN_PACKAGE = "org.apache.commons:commons-lang3:3.14.0"
MAVEN_REPOSITORY = "https://repo1.maven.org/maven2"
REPO_TEXT = "A: B C\nB: C\nC:\n"

REAL_DEFAULTS: Dict[str, Optional[str]] = {
    "package": MAVEN_PACKAGE,
    "repository": MAVEN_REPOSITORY,
    "test_mode": "false",
    "filter": "junit",
}


def build_rows(**overrides: Optional[str]) -> List[str]:
    """Вернуть строки CSV с допустимыми значениями режима Maven.

    Именованные аргументы заменяют значения параметров, а значение
    ``None`` удаляет параметр из файла.
    """
    values = dict(REAL_DEFAULTS)
    values.update(overrides)
    rows = [HEADER_ROW]
    for key, value in values.items():
        if value is not None:
            rows.append(f"{key},{value}")
    return rows
