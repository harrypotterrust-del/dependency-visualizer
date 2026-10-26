"""Тесты проверок отдельных значений параметров."""

import os

import pytest

from depviz import validation


@pytest.mark.parametrize("word", [
    "true", "TRUE", "True", "yes", "YES", "1", "on", "On", " true "])
def test_parse_bool_true(word):
    """Все варианты «истины» распознаются независимо от регистра."""
    assert validation.parse_bool(word) is True


@pytest.mark.parametrize("word", [
    "false", "FALSE", "False", "no", "NO", "0", "off", "OFF"])
def test_parse_bool_false(word):
    """Все варианты «лжи» распознаются независимо от регистра."""
    assert validation.parse_bool(word) is False


@pytest.mark.parametrize("word", ["", "maybe", "2", "tru", "да", "t"])
def test_parse_bool_invalid(word):
    """Остальные значения не являются логическими."""
    assert validation.parse_bool(word) is None


def test_test_mode_message_lists_allowed_values():
    """Сообщение о неверном режиме перечисляет допустимые значения."""
    message = validation.check_test_mode("maybe")
    assert validation.BOOL_HINT in message
    assert "«maybe»" in message


@pytest.mark.parametrize("value", ["A", "ABC", "Z"])
def test_test_package_valid(value):
    """В тестовом режиме имя - заглавные латинские буквы."""
    assert validation.check_package(value, True) is None


@pytest.mark.parametrize("value", ["a", "A1", "A B", "АБ", "A-B", "Ab"])
def test_test_package_invalid(value):
    """Строчные буквы, цифры, пробелы и кириллица недопустимы."""
    assert "заглавных" in validation.check_package(value, True)


@pytest.mark.parametrize("value", [
    "org.apache.commons:commons-lang3",
    "org.apache.commons:commons-lang3:3.14.0",
    "junit:junit:4.13.2",
    "a:b",
    "my_group:my_artifact:1.0-SNAPSHOT",
])
def test_maven_package_valid(value):
    """Допустимы groupId:artifactId и groupId:artifactId:version."""
    assert validation.check_package(value, False) is None


@pytest.mark.parametrize("value", ["lang3", "a:b:c:d", "A:B:C:D:E"])
def test_maven_package_wrong_part_count(value):
    """Число частей должно быть два или три."""
    assert "groupId:artifactId" in validation.check_package(value, False)


@pytest.mark.parametrize("value, part", [
    (":artifact", "groupId"),
    ("group::1.0", "artifactId"),
    ("group:artifact:", "version"),
])
def test_maven_package_empty_part(value, part):
    """Пустая часть координат называется в сообщении."""
    assert part in validation.check_package(value, False)
    assert "пуста" in validation.check_package(value, False)


@pytest.mark.parametrize("value", [
    "org/apache:lib", "org.apache:lib x", "org:lib:1.0+", "гр:ар:1"])
def test_maven_package_bad_chars(value):
    """Недопустимые символы в части координат."""
    assert "может содержать только" in validation.check_package(value, False)


@pytest.mark.parametrize("value", [
    "https://repo1.maven.org/maven2",
    "http://localhost:8080/repo",
    "HTTPS://Example.com",
    "https://user@host.example/path?q=1",
])
def test_url_valid(value):
    """Адреса http и https с хостом принимаются."""
    assert validation.check_repository(value, False, "") is None


@pytest.mark.parametrize("value", [
    "repo1.maven.org/maven2", "maven2", "localhost:8080/repo", "/tmp/x"])
def test_url_without_scheme(value):
    """Без схемы http или https адрес не принимается."""
    assert "http" in validation.check_repository(value, False, "")


def test_url_foreign_scheme():
    """Другие схемы (ftp, file) не принимаются."""
    assert "http" in validation.check_repository("ftp://h/x", False, "")
    assert "http" in validation.check_repository("file:///x", False, "")


def test_url_without_host():
    """Адрес без имени хоста не принимается."""
    message = validation.check_repository("https://", False, "")
    assert "имя хоста" in message


@pytest.mark.parametrize("value", [
    "http://localhost:abc/x", "http://localhost:99999/x"])
def test_url_bad_port(value):
    """Нечисловой порт и порт вне диапазона не принимаются."""
    assert "порт" in validation.check_repository(value, False, "")


def test_url_broken_ipv6():
    """Незакрытый IPv6-адрес не принимается."""
    message = validation.check_repository("http://[::1/x", False, "")
    assert "некорректный URL" in message


def test_url_with_spaces():
    """Пробелы внутри адреса не допускаются."""
    message = validation.check_repository("https://a.b/my repo", False, "")
    assert "пробелов" in message


def test_resolve_path_relative_and_absolute():
    """Относительный путь считается от папки конфигурации."""
    assert validation.resolve_path("cfg/dir", "../r.txt") == "cfg/r.txt"
    assert validation.resolve_path("", "r.txt") == "r.txt"
    assert validation.resolve_path("cfg", "/abs/r.txt") == "/abs/r.txt"


def test_repository_file_ok(repo_file):
    """Существующий обычный файл принимается."""
    assert validation.check_repository_file(repo_file) is None


def test_repository_file_missing(tmp_path):
    """Отсутствующий файл не принимается."""
    path = str(tmp_path / "nope.txt")
    message = validation.check_repository_file(path)
    assert "не найден" in message
    assert path in message


def test_repository_directory(tmp_path):
    """Каталог вместо файла не принимается."""
    message = validation.check_repository_file(str(tmp_path))
    assert "каталог" in message


def test_repository_not_regular_file():
    """Устройство вроде /dev/null существует, но не обычный файл."""
    message = validation.check_repository_file(os.devnull)
    assert "не обычный файл" in message


def test_repository_unreadable(repo_file):
    """Файл без права чтения не принимается."""
    os.chmod(repo_file, 0)
    if os.access(repo_file, os.R_OK):
        pytest.skip("права доступа не ограничивают чтение")
    message = validation.check_repository_file(repo_file)
    assert "нет прав на чтение" in message


@pytest.mark.parametrize("value", [
    "", "junit", "org.apache", "a:b", "A-b_c.d", "123"])
def test_filter_valid(value):
    """Пустой фильтр и безопасные символы допустимы."""
    assert validation.check_filter(value) is None


@pytest.mark.parametrize("value", [
    "two words", "a/b", "star*", "a,b", "кириллица", "a;b", "a\"b"])
def test_filter_invalid(value):
    """Пробелы и посторонние символы в фильтре недопустимы."""
    assert "подстрока фильтра" in validation.check_filter(value)
