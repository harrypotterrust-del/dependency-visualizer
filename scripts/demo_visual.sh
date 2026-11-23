#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
for name in a b c; do
    printf '\n=== Пакет %s ===\n' "$(printf '%s' "$name" | tr a-z A-Z)"
    ./run.sh -c "configs/visual_$name.csv" \
        --visualize "build/dependencies_$name.svg"
done
