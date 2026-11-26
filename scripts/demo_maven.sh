#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
MVN=${MVN:-mvn}
if ! command -v "$MVN" >/dev/null 2>&1; then
    echo "Maven не найден; установите его или задайте MVN" >&2
    exit 1
fi
TMP=${TMPDIR:-/tmp}/depviz-maven-demo.$$
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
for package in \
    org.apache.commons:commons-configuration2:2.11.0 \
    com.google.guava:guava:33.3.1-jre \
    org.apache.logging.log4j:log4j-core:2.24.1 \
    com.fasterxml.jackson.core:jackson-databind:2.18.1
do
    group=${package%%:*}
    rest=${package#*:}
    artifact=${rest%%:*}
    version=${rest##*:}
    dir="$TMP/$artifact"
    mkdir -p "$dir"
    url="https://repo1.maven.org/maven2/$(printf '%s' "$group" | tr . /)"
    url="$url/$artifact/$version/$artifact-$version.pom"
    curl -fsSL "$url" -o "$dir/pom.xml"
    printf 'key,value\npackage,%s\nrepository,%s\ntest_mode,false\nfilter,\n' \
        "$package" "https://repo1.maven.org/maven2" > "$dir/config.csv"
    printf '\n=== %s: depviz ===\n' "$package"
    ./run.sh -c "$dir/config.csv"
    printf '\n=== %s: mvn dependency:tree ===\n' "$package"
    "$MVN" -f "$dir/pom.xml" dependency:tree -Dscope=runtime
done
