"""Чтение CSV-файла конфигурации: файл, заголовок и строки параметров.

Модуль отвечает только за структуру файла (кодировка, заголовок, число
столбцов, неизвестные и повторяющиеся ключи). Допустимость самих
значений проверяется в модуле ``validation``.
"""

import csv
import io
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from depviz.errors import ConfigError, location

HEADER = ["key", "value"]
ENCODING = "utf-8-sig"

Record = Tuple[int, List[str]]


@dataclass(frozen=True)
class Entry:
    """Значение параметра и номер строки файла, где оно записано."""

    value: str
    line: int


def read_text(path: str) -> str:
    """Прочитать файл ``path`` как текст UTF-8.

    Любую проблему доступа или кодировки превращает в ``ConfigError``
    с отдельным понятным сообщением.
    """
    try:
        with open(path, encoding=ENCODING, newline="") as handle:
            return handle.read()
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise ConfigError(
            [f"файл конфигурации не найден: {path}"]) from exc
    except IsADirectoryError as exc:
        raise ConfigError(
            [f"{path} - это каталог, а не файл конфигурации"]) from exc
    except PermissionError as exc:
        raise ConfigError(
            [f"нет прав на чтение файла конфигурации: {path}"]) from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(
            [f"{path}: файл не в кодировке UTF-8"]) from exc
    except OSError as exc:
        raise ConfigError(
            [f"не удалось прочитать файл {path}: {exc.strerror}"]) from exc


def is_blank(row: Sequence[str]) -> bool:
    """Сказать, пуста ли строка CSV (нет ни одной непустой ячейки)."""
    return not any(cell.strip() for cell in row)


def parse_records(path: str, text: str) -> List[Record]:
    """Разобрать текст как CSV и вернуть непустые строки.

    Каждая запись - пара (номер строки, список ячеек). Пустые строки
    пропускаются. Ошибка разбора CSV (например, незакрытая кавычка)
    завершает чтение с ``ConfigError``.
    """
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    records: List[Record] = []
    try:
        for row in reader:
            if not is_blank(row):
                records.append((reader.line_num, row))
    except csv.Error as exc:
        raise ConfigError([
            f"{location(path, reader.line_num)}: "
            f"ошибка разбора CSV, проверьте кавычки ({exc})"]) from exc
    return records


def check_header(path: str, record: Record) -> None:
    """Убедиться, что первая строка файла - заголовок ``key,value``."""
    line, row = record
    if row != HEADER:
        raise ConfigError([
            f"{location(path, line)}: ожидался заголовок "
            f"«{','.join(HEADER)}», получено «{','.join(row)}»"])


def add_entry(entries: Dict[str, Entry], path: str, record: Record,
              allowed_keys: Sequence[str]) -> List[str]:
    """Добавить параметр из строки ``record`` в ``entries``.

    Возвращает список сообщений о проблемах строки (пустой, если
    строка корректна).
    """
    line, row = record
    where = location(path, line)
    if len(row) != len(HEADER):
        return [f"{where}: ожидалось столбцов: {len(HEADER)} "
                f"(ключ и значение), получено: {len(row)}"]
    key, value = row[0].strip(), row[1].strip()
    if key not in allowed_keys:
        return [f"{where}: неизвестный параметр «{key}» "
                f"(допустимые: {', '.join(allowed_keys)})"]
    if key in entries:
        return [f"{where}: параметр «{key}» уже задан "
                f"в строке {entries[key].line}"]
    entries[key] = Entry(value, line)
    return []


def read_entries(path: str, allowed_keys: Sequence[str]
                 ) -> Tuple[Dict[str, Entry], List[str]]:
    """Прочитать файл конфигурации ``path`` в словарь параметров.

    Возвращает пару (параметры, сообщения о проблемах строк). Фатальные
    ошибки файла (нет файла, не UTF-8, пустой файл, неверный заголовок)
    сразу завершают чтение исключением ``ConfigError``.
    """
    records = parse_records(path, read_text(path))
    if not records:
        raise ConfigError([f"{path}: файл конфигурации пуст"])
    check_header(path, records[0])
    entries: Dict[str, Entry] = {}
    problems: List[str] = []
    for record in records[1:]:
        problems.extend(add_entry(entries, path, record, allowed_keys))
    return entries, problems
