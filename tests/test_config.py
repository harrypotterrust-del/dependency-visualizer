"""Тесты загрузки, проверки и вывода параметров конфигурации."""

import os

import pytest

from depviz.config import (ALL_KEYS, Config, REQUIRED_KEYS, format_config,
                           load_config)
from depviz.errors import ConfigError
from samples import MAVEN_PACKAGE, MAVEN_REPOSITORY, build_rows

TRUE_SPELLINGS = ["true", "TRUE", "True", "yes", "YES", "1", "on", "ON"]
FALSE_SPELLINGS = ["false", "FALSE", "False", "no", "NO", "0", "off", "OFF"]
MANY_ERRORS_COUNT = 4
MODE_SKIP_ERRORS_COUNT = 2


def errors_of(path):
    """Вернуть сообщения ``ConfigError``, возникшие при загрузке ``path``."""
    with pytest.raises(ConfigError) as info:
        load_config(path)
    return info.value.messages


def single_error(path):
    """Вернуть единственное сообщение об ошибке при загрузке ``path``."""
    (message,) = errors_of(path)
    return message


def test_load_maven_mode(write_config):
    """Обычный режим: все четыре параметра, путь к файлу не нужен."""
    config = load_config(write_config(build_rows()))
    assert config == Config(package=MAVEN_PACKAGE,
                            repository=MAVEN_REPOSITORY,
                            test_mode=False, package_filter="junit",
                            repository_path=None)


def test_load_test_mode(write_config, repo_file):
    """Тестовый режим: пакет из заглавных букв и существующий файл."""
    rows = build_rows(package="A", repository=repo_file, test_mode="true")
    config = load_config(write_config(rows))
    assert config.test_mode is True
    assert config.package == "A"
    assert config.repository == repo_file
    assert config.repository_path == repo_file


def test_filter_is_optional(write_config):
    """Без параметра ``filter`` фильтр пуст."""
    config = load_config(write_config(build_rows(filter=None)))
    assert config.package_filter == ""


def test_filter_may_be_empty(write_config):
    """Пустое значение ``filter`` допустимо и означает «без фильтра»."""
    config = load_config(write_config(build_rows(filter="")))
    assert config.package_filter == ""


def test_parameter_order_in_file_is_free(write_config):
    """Порядок строк параметров в файле не важен."""
    rows = build_rows()
    shuffled = [rows[0]] + list(reversed(rows[1:]))
    assert load_config(write_config(shuffled)) == load_config(
        write_config(rows, "other.csv"))


def test_quoted_values_are_accepted(write_config):
    """Значения в кавычках читаются как обычные."""
    rows = build_rows(package=f'"{MAVEN_PACKAGE}"',
                      repository=f'"{MAVEN_REPOSITORY}"')
    assert load_config(write_config(rows)).package == MAVEN_PACKAGE


def test_relative_repository_resolves_against_config_dir(
        tmp_path, monkeypatch):
    """Относительный путь считается от папки файла, а не от cwd."""
    (tmp_path / "cfg").mkdir()
    (tmp_path / "repos").mkdir()
    (tmp_path / "repos" / "r.txt").write_text("A:\n", encoding="utf-8")
    rows = build_rows(package="A", repository="../repos/r.txt",
                      test_mode="yes")
    path = tmp_path / "cfg" / "config.csv"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    config = load_config(str(path))
    assert config.repository == "../repos/r.txt"
    assert config.repository_path == str(tmp_path / "repos" / "r.txt")


@pytest.mark.parametrize("spelling", TRUE_SPELLINGS)
def test_true_spellings(write_config, repo_file, spelling):
    """Все записи «истины» включают тестовый режим."""
    rows = build_rows(package="A", repository=repo_file,
                      test_mode=spelling)
    assert load_config(write_config(rows)).test_mode is True


@pytest.mark.parametrize("spelling", FALSE_SPELLINGS)
def test_false_spellings(write_config, spelling):
    """Все записи «лжи» выключают тестовый режим."""
    config = load_config(write_config(build_rows(test_mode=spelling)))
    assert config.test_mode is False


def test_format_config_is_key_value_in_fixed_order(write_config):
    """Вывод - четыре строки ``ключ=значение`` в фиксированном порядке."""
    text = format_config(load_config(write_config(build_rows())))
    assert text.splitlines() == [
        f"package={MAVEN_PACKAGE}",
        f"repository={MAVEN_REPOSITORY}",
        "test_mode=false",
        "filter=junit",
    ]


def test_format_config_normalizes_bool_and_keeps_repository(
        write_config, repo_file):
    """Булево печатается как true/false, репозиторий - как записан."""
    rows = build_rows(package="A", repository=repo_file, test_mode="YES",
                      filter=None)
    lines = format_config(load_config(write_config(rows))).splitlines()
    assert lines == ["package=A", f"repository={repo_file}",
                     "test_mode=true", "filter="]


def test_keys_constants_are_consistent():
    """Обязательные ключи входят в общий список в нужном порядке."""
    assert ALL_KEYS == REQUIRED_KEYS + ("filter",)
    assert ALL_KEYS == ("package", "repository", "test_mode", "filter")


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_missing_required_key(write_config, key):
    """Нет обязательного ключа: сообщение называет ключ и файл."""
    path = write_config(build_rows(**{key: None}))
    assert errors_of(path) == [
        f"{path}: не задан обязательный параметр «{key}»"]


@pytest.mark.parametrize("key, line", [
    ("package", 2), ("repository", 3), ("test_mode", 4)])
def test_empty_required_value(write_config, key, line):
    """Пустое обязательное значение: сообщение с номером строки."""
    path = write_config(build_rows(**{key: ""}))
    assert errors_of(path) == [
        f"{path}, строка {line}: пустое значение "
        f"обязательного параметра «{key}»"]


def test_invalid_test_mode(write_config):
    """Неверный ``test_mode``: сообщение со списком допустимых слов."""
    path = write_config(build_rows(test_mode="maybe"))
    message = single_error(path)
    assert message.startswith(f"{path}, строка 4: параметр «test_mode»")
    assert "true/false, yes/no, 1/0, on/off" in message


def test_package_checked_by_mode(write_config, repo_file):
    """Один и тот же пакет верен в одном режиме и неверен в другом."""
    maven = write_config(build_rows(package="A"))
    assert "координаты Maven" in single_error(maven)
    rows = build_rows(repository=repo_file, test_mode="true")
    assert "заглавных" in single_error(write_config(rows, "t.csv"))


@pytest.mark.parametrize("package", ["a1", "A-B", "Ab", "org:lib"])
def test_invalid_test_package(write_config, repo_file, package):
    """В тестовом режиме пакет - только заглавные латинские буквы."""
    rows = build_rows(package=package, repository=repo_file,
                      test_mode="on")
    message = single_error(write_config(rows))
    assert "параметр «package»" in message


@pytest.mark.parametrize("package", [
    "lang3", "a:b:c:d", "g::1.0", "g:a:", "g/x:a", ":a"])
def test_invalid_maven_package(write_config, package):
    """В обычном режиме пакет - координаты Maven."""
    message = single_error(write_config(build_rows(package=package)))
    assert "параметр «package»" in message
    assert ", строка 2:" in message


@pytest.mark.parametrize("repository", [
    "repo1.maven.org/maven2", "ftp://h/x", "https://", "http://h:port/x",
    "https://a.b/my repo", "repos/simple.txt"])
def test_invalid_repository_url(write_config, repository):
    """В обычном режиме репозиторий - корректный http(s) адрес."""
    message = single_error(write_config(build_rows(repository=repository)))
    assert "параметр «repository»" in message


def test_repository_file_missing(write_config, tmp_path):
    """Тестовый режим: несуществующий файл репозитория."""
    rows = build_rows(package="A", repository="nope.txt", test_mode="1")
    messages = errors_of(write_config(rows))
    expected = os.path.join(str(tmp_path), "nope.txt")
    assert messages[0].endswith(
        f"файл тестового репозитория не найден: {expected}")


def test_repository_is_directory(write_config, tmp_path):
    """Тестовый режим: вместо файла указан каталог."""
    rows = build_rows(package="A", repository=str(tmp_path),
                      test_mode="true")
    assert "каталог" in single_error(write_config(rows))


def test_repository_not_regular_file(write_config):
    """Тестовый режим: существующий, но необычный файл."""
    rows = build_rows(package="A", repository=os.devnull, test_mode="true")
    assert "не обычный файл" in single_error(write_config(rows))


def test_repository_unreadable(write_config, repo_file):
    """Тестовый режим: у файла репозитория нет права чтения."""
    os.chmod(repo_file, 0)
    if os.access(repo_file, os.R_OK):
        pytest.skip("права доступа не ограничивают чтение")
    rows = build_rows(package="A", repository=repo_file, test_mode="true")
    assert "нет прав на чтение" in single_error(write_config(rows))


@pytest.mark.parametrize("value", ["two words", "a/b", "x*", "a,b"])
def test_invalid_filter(write_config, value):
    """Фильтр с пробелами и лишними символами отклоняется."""
    rows = build_rows(filter=f'"{value}"')
    message = single_error(write_config(rows))
    assert "параметр «filter»" in message


def test_all_errors_are_reported_together(write_config):
    """Все ошибки параметров собираются и выдаются сразу."""
    rows = ["key,value", "package,", "repository,ftp://h/x",
            "test_mode,maybe", "filter,a b", "colour,red"]
    path = write_config(rows)
    messages = errors_of(path)
    assert len(messages) == MANY_ERRORS_COUNT
    joined = "\n".join(messages)
    for part in ("неизвестный параметр «colour»",
                 "пустое значение обязательного параметра «package»",
                 "параметр «test_mode»", "параметр «filter»"):
        assert part in joined


def test_invalid_mode_skips_mode_dependent_checks(write_config):
    """Если режим неизвестен, package и repository по режиму не проверяются.

    Режимонезависимые проверки (пустое значение) при этом работают.
    """
    rows = build_rows(package="!!!", repository="", test_mode="maybe")
    messages = errors_of(write_config(rows))
    joined = "\n".join(messages)
    assert "параметр «test_mode»" in joined
    assert "пустое значение обязательного параметра «repository»" in joined
    assert "параметр «package»" not in joined
    assert len(messages) == MODE_SKIP_ERRORS_COUNT


def test_missing_mode_skips_mode_dependent_checks(write_config):
    """Без test_mode проверки package и repository пропускаются."""
    rows = build_rows(package="!!!", repository="???", test_mode=None)
    path = write_config(rows)
    assert errors_of(path) == [
        f"{path}: не задан обязательный параметр «test_mode»"]


def test_structure_problems_come_first_and_do_not_hide_values(
        write_config):
    """Ошибки строк и ошибки значений выдаются одним списком."""
    rows = ["key,value", "package,org:lib,extra", "repository,x",
            "test_mode,false", "filter,ok"]
    path = write_config(rows)
    messages = errors_of(path)
    assert messages[0].startswith(f"{path}, строка 2: ожидалось столбцов")
    assert any("не задан обязательный параметр «package»" in m
               for m in messages)
    assert any("параметр «repository»" in m for m in messages)
