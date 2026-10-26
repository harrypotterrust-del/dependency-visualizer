# Визуализатор графа зависимостей (вариант 5)

Практическая работа 2 по дисциплине «Конфигурационное управление»
(РТУ МИРЭА). Реализован этап 1 - минимальный прототип с конфигурацией.

## 1. Общее описание

Инструмент строит граф зависимостей пакета для менеджера пакетов
(анализируются пакеты Maven). Для получения зависимостей не
используются ни менеджеры пакетов, ни сторонние библиотеки: во время
работы нужна только стандартная библиотека Python 3.8 и новее.
Сторонние пакеты (`flake8` и другие) нужны лишь для проверки стиля и
запуска тестов.

Состояние по этапам:

- **Этап 1 (готов) - минимальный прототип с конфигурацией.** Параметры
  берутся из CSV-файла. При запуске программа проверяет их, печатает в
  формате «ключ=значение» и сообщает о каждой ошибке отдельным
  понятным сообщением.
- Этап 2 (планируется) - получение зависимостей пакета из файлов
  Maven POM.
- Этап 3 (планируется) - построение графа зависимостей рекурсивным
  обходом в глубину (DFS) с учётом подстроки-фильтра и тестового
  репозитория из файла.
- Этап 4 (планируется) - вывод обратных зависимостей: пакетов,
  которые зависят от заданного.
- Этап 5 (планируется) - визуализация графа на языке диаграмм
  PlantUML.

Структура проекта:

```text
.
├── README.md             описание (этот файл)
├── Makefile              цели run, test, lint, check, demo
├── run.sh                запуск программы: ./run.sh [-c PATH]
├── config.csv            конфигурация по умолчанию (копия configs/default.csv)
├── requirements-dev.txt  пакеты для тестов и проверки стиля
├── .flake8, pytest.ini   настройки flake8 и pytest
├── src/depviz/           исходный код
├── tests/                автотесты pytest
├── configs/              примеры конфигураций
│   └── errors/           по одному файлу на каждую ошибку
├── repos/simple.txt      пример файла тестового репозитория
└── scripts/              демонстрационные скрипты demo_ok.sh, demo_errors.sh
```

## 2. Описание всех функций и настроек

### Файл конфигурации

Источник настраиваемых параметров - CSV-файл в кодировке UTF-8
(допускается BOM). Путь к нему задаётся ключом `-c`/`--config`; по
умолчанию читается `config.csv` из текущей папки.

```text
usage: depviz [-h] [-c PATH]

  -c PATH, --config PATH   путь к CSV-файлу конфигурации
                           (по умолчанию: config.csv)
```

Правила формата:

- первая строка - заголовок ровно `key,value`;
- далее по одной строке на параметр: `ключ,значение`;
- файл читается модулем `csv`, поэтому значения можно брать в кавычки;
- пустые строки пропускаются, пробелы вокруг ключа и значения
  срезаются;
- порядок строк любой, ключи различаются по регистру, каждый ключ
  допускается один раз.

Пример (`configs/default.csv`):

```text
key,value
package,org.apache.commons:commons-lang3:3.14.0
repository,https://repo1.maven.org/maven2
test_mode,false
filter,junit
```

### Параметры

| Ключ | Назначение | Допустимые значения | Зависит от режима | По умолчанию |
|---|---|---|---|---|
| `package` | имя анализируемого пакета | тестовый режим: одна или несколько заглавных латинских букв (`A`, `AB`); обычный режим: координаты Maven `groupId:artifactId` или `groupId:artifactId:version`, каждая часть непустая, из символов `A-Za-z0-9._-` | да | обязателен |
| `repository` | адрес репозитория или путь к файлу тестового репозитория | обычный режим: URL со схемой `http` или `https` и именем хоста; тестовый режим: путь к существующему читаемому обычному файлу (относительный путь отсчитывается от папки CSV-файла) | да | обязателен |
| `test_mode` | режим тестового репозитория | `true/false`, `yes/no`, `1/0`, `on/off` в любом регистре | нет, сам задаёт режим для `package` и `repository` | обязателен |
| `filter` | подстрока для фильтрации пакетов | символы `A-Za-z0-9._:-` без пробелов; пустая строка - без фильтрации | нет | пустая строка |

Вывод при успешной проверке (код завершения 0), порядок строк
фиксирован. Логическое значение печатается нормализованным
(`true`/`false`), `repository` - так, как записан в файле:

```text
package=org.apache.commons:commons-lang3:3.14.0
repository=https://repo1.maven.org/maven2
test_mode=false
filter=junit
```

Формат файла тестового репозитория (`repos/simple.txt`, понадобится на
следующих этапах): одна строка на пакет, имя пакета - заглавные
латинские буквы, после двоеточия через пробел перечислены его
зависимости.

```text
A: B C
B: C D
C: D
D:
```

### Обработка ошибок

Каждая ошибка печатается в stderr отдельной строкой вида
`ошибка: <сообщение>`, код завершения 1. Сообщение указывает файл и,
если возможно, номер строки. Ошибки самих аргументов командной строки
обрабатывает `argparse`: он печатает справку по использованию и
завершает программу с кодом 2.

**Ошибки файла - чтение останавливается на первой из них:**

| Ситуация | Сообщение |
|---|---|
| файла нет | `файл конфигурации не найден: <путь>` |
| вместо файла каталог | `<путь> - это каталог, а не файл конфигурации` |
| нет права чтения | `нет прав на чтение файла конфигурации: <путь>` |
| другая ошибка чтения | `не удалось прочитать файл <путь>: <причина>` |
| не UTF-8 | `<путь>: файл не в кодировке UTF-8` |
| сломан CSV (например, не закрыта кавычка) | `<путь>, строка N: ошибка разбора CSV, проверьте кавычки (<причина>)` |
| файл пуст | `<путь>: файл конфигурации пуст` |
| неверный заголовок | `<путь>, строка N: ожидался заголовок «key,value», получено «...»` |

**Ошибки строк и параметров - собираются и выводятся все сразу.**
Сначала идут ошибки строк в порядке следования в файле, затем ошибки
параметров в порядке `package`, `repository`, `test_mode`, `filter`:

| Ситуация | Сообщение |
|---|---|
| не два столбца | `<путь>, строка N: ожидалось столбцов: 2 (ключ и значение), получено: K` |
| неизвестный ключ | `<путь>, строка N: неизвестный параметр «x» (допустимые: package, repository, test_mode, filter)` |
| повтор ключа | `<путь>, строка N: параметр «x» уже задан в строке M` |
| нет обязательного ключа | `<путь>: не задан обязательный параметр «x»` |
| пустое обязательное значение | `<путь>, строка N: пустое значение обязательного параметра «x»` |
| неверный `test_mode` | `<путь>, строка N: параметр «test_mode»: ожидается одно из значений: true/false, yes/no, 1/0, on/off (регистр не важен), получено «...»` |
| неверный `package` | причина зависит от режима: не заглавные латинские буквы; число частей координат Maven не 2 или 3; пустая часть; недопустимые символы в части |
| неверный `repository` (обычный режим) | нет схемы `http`/`https`; нет имени хоста; некорректный порт; пробелы в адресе; нераспознаваемый URL |
| неверный `repository` (тестовый режим) | файл не найден; указан каталог; не обычный файл (например, устройство); нет права чтения |
| неверный `filter` | `подстрока фильтра может содержать только латинские буквы, цифры и символы . _ : - (без пробелов)` |

Зависимость от режима: `package` и `repository` проверяются только
когда `test_mode` задан и корректен. Если он отсутствует, пуст или
неверен, об этом сообщается отдельно, а проверки, зависящие от режима,
пропускаются; проверки, не зависящие от режима (пустые значения,
повторы, лишние ключи, `filter`), выполняются всегда.

### Модули и функции

Пакет `src/depviz/`:

- `__main__.py` - точка входа `python3 -m depviz`, вызывает `cli.main`.
- `cli.py` - интерфейс командной строки.
  - `build_parser()` - разборщик аргументов (`-c/--config`).
  - `report_errors(error)` - печатает сообщения `ConfigError` в stderr.
  - `main(argv)` - загружает конфигурацию, печатает параметры или
    ошибки, возвращает код завершения (`EXIT_OK` = 0, `EXIT_ERROR` = 1).
- `config.py` - параметры и их проверка.
  - `Config` - неизменяемая запись проверенных параметров
    (`package`, `repository`, `test_mode`, `package_filter`,
    `repository_path`).
  - `load_config(path)` - читает файл, проверяет всё и возвращает
    `Config` либо бросает `ConfigError` со всеми сообщениями.
  - `format_config(config)` - строки `ключ=значение`.
  - `find_errors`, `check_required`, `check_entry`, `build_checks` -
    небольшие функции проверки параметров; `build_config` собирает
    `Config`.
- `reader.py` - чтение структуры CSV.
  - `read_text(path)` - чтение файла с понятными ошибками доступа и
    кодировки.
  - `parse_records(path, text)`, `check_header(path, record)` -
    разбор CSV и проверка заголовка.
  - `add_entry(...)`, `read_entries(path, allowed_keys)` - разбор строк
    параметров: число столбцов, неизвестные и повторяющиеся ключи.
- `validation.py` - проверки значений: `parse_bool`, `check_test_mode`,
  `check_package` (`check_test_package`, `check_maven_package`),
  `check_repository` (`check_repository_url`, `check_repository_file`),
  `check_filter`, `resolve_path`. Каждая `check_*` возвращает `None` или
  текст причины.
- `errors.py` - исключение `ConfigError` (список сообщений) и
  `location(path, line)` для подписи места ошибки.

## 3. Команды для сборки и запуска тестов

Сборка не нужна. Для тестов и проверки стиля создаётся виртуальное
окружение:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Основные команды (без активации окружения интерпретатор задаётся
переменной `PYTHON`, например `make PYTHON=.venv/bin/python test`):

```sh
make run ARGS="-c configs/test_mode.csv"  # запуск программы
./run.sh                                  # то же без make, читает config.csv
make test                                 # автотесты pytest
make lint                                 # проверка стиля flake8
make check                                # lint + test
make demo                                 # оба демонстрационных скрипта
```

Проверка стиля (`.flake8`): строки до 80 символов, функции до 40
строк, не больше 7 аргументов, цикломатическая сложность до 10,
docstring у каждого модуля, класса и функции, имена по PEP 8. Числа
в сравнениях вынесены в именованные константы.

Тесты (`tests/`, pytest, 209 проверок):

- `test_validation.py` - проверка каждого значения отдельно;
- `test_reader.py` - ошибки файла и строк CSV;
- `test_config.py` - загрузка в обоих режимах, варианты логического
  значения, все сообщения об ошибках, вывод `ключ=значение`;
- `test_cli.py` - коды завершения 0, 1 и 2, stdout и stderr, запуск
  `python -m depviz` отдельным процессом;
- `test_examples.py` - все файлы из `configs/` загружаются, все из
  `configs/errors/` дают ошибку.

## 4. Примеры использования

Команды выполняются из корня проекта. Вывод ниже - настоящий вывод
программы; `[код завершения: N]` добавлен для наглядности.

### Успешный запуск

Без аргументов (`config.csv`) и тестовый режим:

```text
$ ./run.sh
package=org.apache.commons:commons-lang3:3.14.0
repository=https://repo1.maven.org/maven2
test_mode=false
filter=junit
[код завершения: 0]
```

```text
$ ./run.sh -c configs/test_mode.csv
package=A
repository=../repos/simple.txt
test_mode=true
filter=C
[код завершения: 0]
```

### Ошибки файла

```text
$ ./run.sh -c configs/no-such-file.csv
ошибка: файл конфигурации не найден: configs/no-such-file.csv
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors
ошибка: configs/errors - это каталог, а не файл конфигурации
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/empty.csv
ошибка: configs/errors/empty.csv: файл конфигурации пуст
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/bad_header.csv
ошибка: configs/errors/bad_header.csv, строка 1: ожидался заголовок «key,value», получено «name,value»
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/broken_quote.csv
ошибка: configs/errors/broken_quote.csv, строка 4: ошибка разбора CSV, проверьте кавычки (unexpected end of data)
[код завершения: 1]
```

### Ошибки строк

```text
$ ./run.sh -c configs/errors/bad_columns.csv
ошибка: configs/errors/bad_columns.csv, строка 3: ожидалось столбцов: 2 (ключ и значение), получено: 3
ошибка: configs/errors/bad_columns.csv, строка 5: ожидалось столбцов: 2 (ключ и значение), получено: 1
ошибка: configs/errors/bad_columns.csv: не задан обязательный параметр «repository»
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/unknown_key.csv
ошибка: configs/errors/unknown_key.csv, строка 5: неизвестный параметр «colour» (допустимые: package, repository, test_mode, filter)
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/duplicate_key.csv
ошибка: configs/errors/duplicate_key.csv, строка 5: параметр «package» уже задан в строке 2
[код завершения: 1]
```

### Ошибки значений

```text
$ ./run.sh -c configs/errors/missing_package.csv
ошибка: configs/errors/missing_package.csv: не задан обязательный параметр «package»
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/empty_repository.csv
ошибка: configs/errors/empty_repository.csv, строка 3: пустое значение обязательного параметра «repository»
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/test_mode_invalid.csv
ошибка: configs/errors/test_mode_invalid.csv, строка 4: параметр «test_mode»: ожидается одно из значений: true/false, yes/no, 1/0, on/off (регистр не важен), получено «maybe»
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/package_bad_parts.csv
ошибка: configs/errors/package_bad_parts.csv, строка 2: параметр «package»: координаты Maven должны иметь вид groupId:artifactId или groupId:artifactId:version, получено «commons-lang3»
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/package_bad_test.csv
ошибка: configs/errors/package_bad_test.csv, строка 2: параметр «package»: в тестовом режиме имя пакета - одна или несколько заглавных латинских букв (например, A), получено «a1»
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/repository_bad_scheme.csv
ошибка: configs/errors/repository_bad_scheme.csv, строка 3: параметр «repository»: URL должен начинаться со схемы http:// или https://, получено «ftp://repo1.maven.org/maven2»
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/repository_file_missing.csv
ошибка: configs/errors/repository_file_missing.csv, строка 3: параметр «repository»: файл тестового репозитория не найден: repos/missing.txt
[код завершения: 1]
```

```text
$ ./run.sh -c configs/errors/filter_bad_chars.csv
ошибка: configs/errors/filter_bad_chars.csv, строка 5: параметр «filter»: подстрока фильтра может содержать только латинские буквы, цифры и символы . _ : - (без пробелов), получено «junit test*»
[код завершения: 1]
```

### Несколько ошибок сразу

```text
$ ./run.sh -c configs/errors/many_errors.csv
ошибка: configs/errors/many_errors.csv, строка 6: неизвестный параметр «colour» (допустимые: package, repository, test_mode, filter)
ошибка: configs/errors/many_errors.csv, строка 7: параметр «package» уже задан в строке 2
ошибка: configs/errors/many_errors.csv, строка 2: пустое значение обязательного параметра «package»
ошибка: configs/errors/many_errors.csv, строка 4: параметр «test_mode»: ожидается одно из значений: true/false, yes/no, 1/0, on/off (регистр не важен), получено «maybe»
ошибка: configs/errors/many_errors.csv, строка 5: параметр «filter»: подстрока фильтра может содержать только латинские буквы, цифры и символы . _ : - (без пробелов), получено «a b»
[код завершения: 1]
```

### Ошибки аргументов

```text
$ ./run.sh --unknown
usage: depviz [-h] [-c PATH]
depviz: error: unrecognized arguments: --unknown
[код завершения: 2]
```

### Все примеры

Скрипты `scripts/demo_ok.sh` и `scripts/demo_errors.sh` (или `make demo`)
запускают программу на всех примерах и печатают заголовок с именем файла
перед каждым запуском. Ошибки, которые нельзя хранить в репозитории
готовым файлом (не UTF-8, нет права чтения), скрипт создаёт во
временной папке:

```text
$ scripts/demo_errors.sh
...
--- ошибки файла, которых нет среди готовых примеров ---
=== configs/no-such-file.csv ===
ошибка: файл конфигурации не найден: configs/no-such-file.csv
код завершения: 1
=== configs/errors ===
ошибка: configs/errors - это каталог, а не файл конфигурации
код завершения: 1
=== (временный файл) not_utf8.csv ===
ошибка: not_utf8.csv: файл не в кодировке UTF-8
код завершения: 1
=== (временный файл) no_access.csv ===
ошибка: нет прав на чтение файла конфигурации: no_access.csv
код завершения: 1
...
```

Готовые примеры ошибочных конфигураций в `configs/errors/`:

| Файл | Что демонстрирует |
|---|---|
| `empty.csv` | пустой файл |
| `bad_header.csv`, `no_header.csv` | неверный заголовок; заголовка нет |
| `bad_columns.csv` | строки с лишними и недостающими столбцами |
| `unknown_key.csv`, `duplicate_key.csv` | неизвестный и повторяющийся ключ |
| `broken_quote.csv` | не закрыта кавычка |
| `missing_package.csv`, `missing_repository.csv`, `missing_test_mode.csv` | нет обязательного ключа |
| `empty_package.csv`, `empty_repository.csv`, `empty_test_mode.csv` | пустое обязательное значение |
| `test_mode_invalid.csv` | недопустимое значение `test_mode` |
| `package_bad_test.csv` | пакет тестового режима не из заглавных букв |
| `package_bad_parts.csv`, `package_empty_part.csv`, `package_bad_chars.csv` | неверные координаты Maven |
| `repository_no_scheme.csv`, `repository_bad_scheme.csv`, `repository_no_host.csv`, `repository_bad_port.csv`, `repository_spaces.csv` | неверный URL |
| `repository_file_missing.csv`, `repository_is_directory.csv`, `repository_not_regular.csv` | неверный файл тестового репозитория |
| `filter_bad_chars.csv` | недопустимые символы в фильтре |
| `many_errors.csv` | сразу несколько ошибок |
