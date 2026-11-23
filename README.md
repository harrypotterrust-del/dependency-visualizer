# Визуализатор зависимостей Maven — вариант 5

## Этап 3: граф зависимостей

CLI строит транзитивный граф рекурсивным DFS. Поддерживаются Maven Central
и тестовый репозиторий, фильтрация по подстроке и циклические зависимости.
Maven и сторонние библиотеки получения зависимостей не используются:
HTTP-запросы выполняет `urllib`, XML разбирает `ElementTree`.

Предыдущие этапы находятся в ветках `stage-1` и `stage-2`. Следующие этапы
добавят обратные зависимости и визуализацию.

## Конфигурация

Файл CSV содержит заголовок `key,value` и параметры:

```csv
key,value
package,org.apache.commons:commons-lang3:3.14.0
repository,https://repo1.maven.org/maven2
test_mode,false
filter,
```

- `package` — `groupId:artifactId:version`; если версия не указана,
  программа читает `maven-metadata.xml` и выбирает release/latest.
- `repository` — базовый URL репозитория HTTP/HTTPS.
- `test_mode=false` — работа с Maven; тестовые файлы появятся на этапе 3.
- `filter` — зарезервирован для этапа 3.

Учитываются зависимости со scope `compile` (по умолчанию) и `runtime`.
Зависимости `test`, `provided`, `system` и `optional=true` пропускаются.
Поддерживаются XML namespace и подстановки `${property}` в координатах.

## Запуск

Требуется Python 3.8+ и доступ к репозиторию:

```sh
./run.sh
./run.sh -c configs/default.csv
```

Каждая зависимость выводится строкой `groupId:artifactId:version`.
Ошибки конфигурации, HTTP и XML выводятся в stderr; код ошибки — 1.

## Тесты

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
make test
make lint
```

`src/depviz/maven.py` формирует URL POM, скачивает его и извлекает
зависимости. `src/depviz/cli.py` связывает конфигурацию и вывод.
`tests/test_maven.py` проверяет разбор POM, а остальные тесты — конфигурацию
и CLI.
