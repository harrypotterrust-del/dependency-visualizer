"""Проверка значений параметров конфигурации.

Функции ``check_*`` принимают значение без пробелов по краям и
возвращают ``None``, если оно корректно, иначе - текст причины ошибки.
Место ошибки (файл и строку) добавляет вызывающий код.
"""

import os
import re
from typing import Optional
from urllib.parse import SplitResult, urlsplit

TRUE_WORDS = ("true", "yes", "1", "on")
FALSE_WORDS = ("false", "no", "0", "off")
BOOL_HINT = "true/false, yes/no, 1/0, on/off"

TEST_PACKAGE = re.compile(r"[A-Z]+")
MAVEN_PART = re.compile(r"[A-Za-z0-9._-]+")
FILTER_TEXT = re.compile(r"[A-Za-z0-9._:-]*")
WHITESPACE = re.compile(r"\s")

MAVEN_PART_NAMES = ("groupId", "artifactId", "version")
MAVEN_PART_COUNTS = (2, 3)
URL_SCHEMES = ("http", "https")


def parse_bool(value: str) -> Optional[bool]:
    """Разобрать логическое значение; вернуть ``None``, если оно неверно.

    Допустимы ``true/false``, ``yes/no``, ``1/0``, ``on/off`` в любом
    регистре.
    """
    word = value.strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    return None


def check_test_mode(value: str) -> Optional[str]:
    """Проверить значение параметра ``test_mode``."""
    if parse_bool(value) is None:
        return (f"ожидается одно из значений: {BOOL_HINT} "
                f"(регистр не важен), получено «{value}»")
    return None


def check_test_package(value: str) -> Optional[str]:
    """Проверить имя пакета тестового репозитория (заглавные буквы)."""
    if TEST_PACKAGE.fullmatch(value):
        return None
    return ("в тестовом режиме имя пакета - одна или несколько заглавных "
            f"латинских букв (например, A), получено «{value}»")


def check_maven_part(name: str, part: str) -> Optional[str]:
    """Проверить одну часть координат Maven (``name`` - её название)."""
    if not part:
        return f"часть {name} координат Maven пуста"
    if not MAVEN_PART.fullmatch(part):
        return (f"часть {name} («{part}») может содержать только "
                "латинские буквы, цифры, точку, дефис и подчёркивание")
    return None


def check_maven_package(value: str) -> Optional[str]:
    """Проверить координаты Maven ``groupId:artifactId[:version]``."""
    parts = value.split(":")
    if len(parts) not in MAVEN_PART_COUNTS:
        return ("координаты Maven должны иметь вид groupId:artifactId "
                f"или groupId:artifactId:version, получено «{value}»")
    for name, part in zip(MAVEN_PART_NAMES, parts):
        reason = check_maven_part(name, part)
        if reason:
            return reason
    return None


def check_package(value: str, test_mode: bool) -> Optional[str]:
    """Проверить имя пакета с учётом режима (тестовый или Maven)."""
    if test_mode:
        return check_test_package(value)
    return check_maven_package(value)


def has_valid_port(parts: SplitResult) -> bool:
    """Сказать, что порт в URL (если он есть) - допустимое число.

    Свойство ``port`` само бросает ``ValueError`` для нечислового порта
    и для порта вне диапазона 0-65535.
    """
    try:
        parts.port
    except ValueError:
        return False
    return True


def check_repository_url(value: str) -> Optional[str]:
    """Проверить, что значение - адрес http или https с именем хоста."""
    if WHITESPACE.search(value):
        return f"в URL «{value}» не должно быть пробелов"
    try:
        parts = urlsplit(value)
    except ValueError:
        return f"некорректный URL «{value}»"
    if parts.scheme.lower() not in URL_SCHEMES:
        return ("URL должен начинаться со схемы http:// или https://, "
                f"получено «{value}»")
    if not parts.hostname:
        return f"в URL «{value}» не указано имя хоста"
    if not has_valid_port(parts):
        return f"в URL «{value}» некорректный порт"
    return None


def resolve_path(base_dir: str, value: str) -> str:
    """Вернуть путь из конфигурации относительно папки файла ``base_dir``.

    Абсолютный путь остаётся как есть, относительный отсчитывается
    от папки, где лежит файл конфигурации.
    """
    return os.path.normpath(os.path.join(base_dir, value))


def check_repository_file(path: str) -> Optional[str]:
    """Проверить, что ``path`` - существующий читаемый обычный файл."""
    if not os.path.exists(path):
        return f"файл тестового репозитория не найден: {path}"
    if os.path.isdir(path):
        return f"{path} - это каталог, а не файл тестового репозитория"
    if not os.path.isfile(path):
        return f"{path} - не обычный файл"
    if not os.access(path, os.R_OK):
        return f"нет прав на чтение файла тестового репозитория: {path}"
    return None


def check_repository(value: str, test_mode: bool,
                     base_dir: str) -> Optional[str]:
    """Проверить репозиторий: файл в тестовом режиме, иначе URL."""
    if test_mode:
        return check_repository_file(resolve_path(base_dir, value))
    return check_repository_url(value)


def check_filter(value: str) -> Optional[str]:
    """Проверить подстроку фильтра пакетов (пустая строка допустима)."""
    if FILTER_TEXT.fullmatch(value):
        return None
    return ("подстрока фильтра может содержать только латинские буквы, "
            "цифры и символы . _ : - (без пробелов), "
            f"получено «{value}»")
