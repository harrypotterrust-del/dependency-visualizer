#!/bin/sh
# Демонстрация успешных запусков: обычный и тестовый режимы.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

for config in configs/default.csv configs/test_mode.csv; do
    echo "=== $config ==="
    ./run.sh -c "$config"
    echo "код завершения: $?"
done

echo "=== без аргументов (config.csv) ==="
./run.sh
echo "код завершения: $?"
