"""Тесты чтения файла конфигурации: структура CSV и ошибки файла."""

import os

import pytest

from depviz.config import ALL_KEYS
from depviz.errors import ConfigError
from depviz.reader import Entry, read_entries

FIRST_PARAM_LINE = 2
THIRD_PARAM_LINE = 4


def messages_of(path):
    """Вернуть все сообщения ``ConfigError`` при чтении файла ``path``."""
    with pytest.raises(ConfigError) as info:
        read_entries(path, ALL_KEYS)
    return info.value.messages


def problems_of(path):
    """Вернуть сообщения о проблемах строк (они не фатальны)."""
    return read_entries(path, ALL_KEYS)[1]


def test_reads_entries_with_line_numbers(write_config):
    """Параметры читаются вместе с номерами их строк."""
    path = write_config(["key,value", "package,A", "", "filter,C"])
    entries, problems = read_entries(path, ALL_KEYS)
    assert entries == {
        "package": Entry("A", FIRST_PARAM_LINE),
        "filter": Entry("C", THIRD_PARAM_LINE),
    }
    assert problems == []


def test_blank_rows_and_spaces_are_ignored(write_config):
    """Пустые строки пропускаются, пробелы по краям срезаются."""
    path = write_config(["", "key,value", "  ", ",", " package , A ", ""])
    entries, problems = read_entries(path, ALL_KEYS)
    assert entries["package"].value == "A"
    assert problems == []


def test_quoted_value_with_comma_is_one_cell(write_config):
    """Значение в кавычках с запятой - одна ячейка."""
    path = write_config(['key,value', 'filter,"a,b"'])
    entries, _ = read_entries(path, ALL_KEYS)
    assert entries["filter"].value == "a,b"


def test_crlf_and_bom_are_accepted(tmp_path):
    """Windows-переводы строк и BOM в начале файла не мешают."""
    path = tmp_path / "win.csv"
    path.write_bytes(b"\xef\xbb\xbfkey,value\r\npackage,A\r\n")
    entries, problems = read_entries(str(path), ALL_KEYS)
    assert entries["package"].value == "A"
    assert problems == []


def test_file_not_found(tmp_path):
    """Отсутствующий файл: одно сообщение с путём."""
    path = str(tmp_path / "nope.csv")
    assert messages_of(path) == [f"файл конфигурации не найден: {path}"]


def test_parent_is_a_file(tmp_path):
    """Путь «внутри файла» тоже считается отсутствующим файлом."""
    base = tmp_path / "plain.txt"
    base.write_text("x", encoding="utf-8")
    path = str(base / "config.csv")
    assert messages_of(path) == [f"файл конфигурации не найден: {path}"]


def test_path_is_directory(tmp_path):
    """Каталог вместо файла: отдельное сообщение."""
    path = str(tmp_path)
    assert messages_of(path) == [
        f"{path} - это каталог, а не файл конфигурации"]


def test_not_utf8(tmp_path):
    """Файл не в UTF-8: отдельное сообщение."""
    path = tmp_path / "bad.csv"
    path.write_bytes(b"key,value\npackage,\xff\xfe\n")
    assert messages_of(str(path)) == [
        f"{path}: файл не в кодировке UTF-8"]


def test_permission_denied(write_config):
    """Файл без права чтения: отдельное сообщение."""
    path = write_config(["key,value"])
    os.chmod(path, 0)
    if os.access(path, os.R_OK):
        pytest.skip("права доступа не ограничивают чтение")
    assert messages_of(path) == [
        f"нет прав на чтение файла конфигурации: {path}"]


def test_empty_file(tmp_path):
    """Файл нулевой длины пуст."""
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")
    assert messages_of(str(path)) == [f"{path}: файл конфигурации пуст"]


def test_only_blank_rows_is_empty(tmp_path):
    """Файл из одних пустых строк тоже пуст."""
    path = tmp_path / "blank.csv"
    path.write_text("\n  \n,\n", encoding="utf-8")
    assert messages_of(str(path)) == [f"{path}: файл конфигурации пуст"]


@pytest.mark.parametrize("header", [
    "name,value", "key", "key,value,extra", "Key,Value", "value,key"])
def test_wrong_header(write_config, header):
    """Заголовок должен быть ровно ``key,value``."""
    path = write_config([header, "package,A"])
    assert messages_of(path) == [
        f"{path}, строка 1: ожидался заголовок «key,value», "
        f"получено «{header}»"]


def test_missing_header(write_config):
    """Первая строка с данными вместо заголовка - ошибка заголовка."""
    path = write_config(["package,A", "filter,C"])
    assert messages_of(path)[0].startswith(
        f"{path}, строка 1: ожидался заголовок")


def test_wrong_column_count_reports_line(write_config):
    """Строки с чужим числом столбцов названы по номеру."""
    path = write_config(["key,value", "package,A,x", "filter", "ok,1,2,3"])
    assert problems_of(path) == [
        f"{path}, строка 2: ожидалось столбцов: 2 (ключ и значение), "
        "получено: 3",
        f"{path}, строка 3: ожидалось столбцов: 2 (ключ и значение), "
        "получено: 1",
        f"{path}, строка 4: ожидалось столбцов: 2 (ключ и значение), "
        "получено: 4",
    ]


def test_unknown_key_lists_allowed_keys(write_config):
    """Неизвестный ключ: номер строки и список допустимых ключей."""
    path = write_config(["key,value", "package,A", "colour,red"])
    assert problems_of(path) == [
        f"{path}, строка 3: неизвестный параметр «colour» "
        "(допустимые: package, repository, test_mode, filter)"]


def test_key_names_are_case_sensitive(write_config):
    """Ключи различаются по регистру."""
    path = write_config(["key,value", "Package,A"])
    assert problems_of(path)[0].startswith(
        f"{path}, строка 2: неизвестный параметр «Package»")


def test_duplicate_key_reports_both_lines(write_config):
    """Повтор ключа: номер повторной и первой строки; значение первое."""
    path = write_config(["key,value", "package,A", "filter,C", "package,B"])
    entries, problems = read_entries(path, ALL_KEYS)
    assert entries["package"].value == "A"
    assert problems == [
        f"{path}, строка 4: параметр «package» уже задан в строке 2"]


def test_unclosed_quote_is_csv_error(write_config):
    """Незакрытая кавычка: ошибка разбора CSV с номером строки."""
    path = write_config(['key,value', 'package,"A', "filter,C"])
    messages = messages_of(path)
    assert messages[0].startswith(f"{path}, строка 3: ошибка разбора CSV")
