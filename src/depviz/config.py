"""Параметры программы: загрузка из CSV, проверка и вывод.

Файл конфигурации - таблица ``key,value``. Допустимые параметры:
``package``, ``repository``, ``test_mode`` и необязательный ``filter``.
"""

import os
from dataclasses import dataclass
from functools import partial
from typing import Callable, Dict, List, Optional, Tuple

from depviz import validation
from depviz.errors import ConfigError, location
from depviz.reader import Entry, read_entries

DEFAULT_CONFIG = "config.csv"

KEY_PACKAGE = "package"
KEY_REPOSITORY = "repository"
KEY_TEST_MODE = "test_mode"
KEY_FILTER = "filter"
REQUIRED_KEYS = (KEY_PACKAGE, KEY_REPOSITORY, KEY_TEST_MODE)
ALL_KEYS = REQUIRED_KEYS + (KEY_FILTER,)

Entries = Dict[str, Entry]
Check = Callable[[str], Optional[str]]


@dataclass(frozen=True)
class Config:
    """Проверенные параметры анализа зависимостей.

    ``repository`` хранится так, как записан в файле; в тестовом режиме
    ``repository_path`` - абсолютный путь к файлу тестового репозитория,
    а в обычном режиме - ``None``.
    """

    package: str
    repository: str
    test_mode: bool
    package_filter: str = ""
    repository_path: Optional[str] = None


def format_bool(value: bool) -> str:
    """Записать логическое значение как ``true`` или ``false``."""
    return "true" if value else "false"


def format_config(config: Config) -> str:
    """Сформировать вывод всех параметров в формате ``ключ=значение``."""
    pairs = [
        (KEY_PACKAGE, config.package),
        (KEY_REPOSITORY, config.repository),
        (KEY_TEST_MODE, format_bool(config.test_mode)),
        (KEY_FILTER, config.package_filter),
    ]
    return "\n".join(f"{key}={value}" for key, value in pairs)


def config_dir(path: str) -> str:
    """Вернуть папку файла конфигурации (для относительных путей)."""
    return os.path.dirname(path)


def check_required(path: str, entries: Entries) -> List[str]:
    """Найти пропущенные обязательные параметры и пустые значения."""
    errors = []
    for key in REQUIRED_KEYS:
        entry = entries.get(key)
        if entry is None:
            errors.append(f"{path}: не задан обязательный параметр «{key}»")
        elif not entry.value:
            errors.append(f"{location(path, entry.line)}: пустое значение "
                          f"обязательного параметра «{key}»")
    return errors


def parse_mode(entries: Entries) -> Optional[bool]:
    """Вернуть режим из ``test_mode`` или ``None``, если он неизвестен."""
    entry = entries.get(KEY_TEST_MODE)
    if entry is None:
        return None
    return validation.parse_bool(entry.value)


def check_entry(path: str, entries: Entries, key: str,
                check: Check) -> Optional[str]:
    """Проверить непустое значение параметра ``key`` функцией ``check``.

    Пустые и отсутствующие значения здесь пропускаются: о них уже
    сообщает ``check_required``.
    """
    entry = entries.get(key)
    if entry is None or not entry.value:
        return None
    reason = check(entry.value)
    if reason is None:
        return None
    return f"{location(path, entry.line)}: параметр «{key}»: {reason}"


def build_checks(test_mode: Optional[bool],
                 base_dir: str) -> List[Tuple[str, Check]]:
    """Составить список проверок значений в порядке параметров.

    Проверки ``package`` и ``repository`` зависят от режима, поэтому
    при неизвестном режиме (``None``) они пропускаются.
    """
    checks: List[Tuple[str, Check]] = []
    if test_mode is not None:
        checks.append((KEY_PACKAGE, partial(
            validation.check_package, test_mode=test_mode)))
        checks.append((KEY_REPOSITORY, partial(
            validation.check_repository, test_mode=test_mode,
            base_dir=base_dir)))
    checks.append((KEY_TEST_MODE, validation.check_test_mode))
    checks.append((KEY_FILTER, validation.check_filter))
    return checks


def find_errors(path: str, entries: Entries) -> List[str]:
    """Проверить все параметры и вернуть сообщения обо всех ошибках."""
    errors = check_required(path, entries)
    checks = build_checks(parse_mode(entries), config_dir(path))
    for key, check in checks:
        message = check_entry(path, entries, key, check)
        if message:
            errors.append(message)
    return errors


def build_config(path: str, entries: Entries) -> Config:
    """Собрать ``Config`` из параметров, уже прошедших проверку."""
    test_mode = parse_mode(entries) is True
    repository = entries[KEY_REPOSITORY].value
    filter_entry = entries.get(KEY_FILTER)
    repository_path = None
    if test_mode:
        repository_path = os.path.abspath(
            validation.resolve_path(config_dir(path), repository))
    return Config(
        package=entries[KEY_PACKAGE].value,
        repository=repository,
        test_mode=test_mode,
        package_filter=filter_entry.value if filter_entry else "",
        repository_path=repository_path,
    )


def load_config(path: str) -> Config:
    """Прочитать и проверить файл конфигурации ``path``.

    При любых проблемах бросает ``ConfigError`` сразу со всеми
    найденными сообщениями.
    """
    entries, errors = read_entries(path, ALL_KEYS)
    errors.extend(find_errors(path, entries))
    if errors:
        raise ConfigError(errors)
    return build_config(path, entries)
