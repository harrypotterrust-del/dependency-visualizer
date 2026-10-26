#!/bin/sh
# Демонстрация обработки ошибок: каждый файл из configs/errors/ и
# ошибки, которые нельзя хранить в репозитории как обычный файл.
# Скрипт не останавливается на ненулевом коде завершения.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

run_config() {
    echo "=== $1 ==="
    ./run.sh -c "$1"
    echo "код завершения: $?"
}

for config in configs/errors/*.csv; do
    run_config "$config"
done

echo "--- ошибки файла, которых нет среди готовых примеров ---"
run_config configs/no-such-file.csv
run_config configs/errors

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
printf 'key,value\npackage,\377\376\n' > "$TMP/not_utf8.csv"
printf 'key,value\n' > "$TMP/no_access.csv"
chmod 000 "$TMP/no_access.csv"
for name in not_utf8.csv no_access.csv; do
    echo "=== (временный файл) $name ==="
    (cd "$TMP" && "$ROOT/run.sh" -c "$name")
    echo "код завершения: $?"
done

echo "--- ошибки аргументов командной строки ---"
for args in "--config" "--unknown"; do
    echo "=== run.sh $args ==="
    ./run.sh $args
    echo "код завершения: $?"
done
