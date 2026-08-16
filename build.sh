#!/usr/bin/env bash
# Собирает Python-пакет (wheel + sdist) в dist/ с текущей версией из
# pyproject.toml. Версия увеличивается автоматически только в CI при пуше
# в main (.github/workflows/release.yml, scripts/bump_version.py) — этот
# скрипт версию не трогает, чтобы локальные сборки не расходились с тем,
# что уже закоммичено.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! python3 -c "import build" >/dev/null 2>&1; then
    echo "Ошибка: не найден модуль 'build'. Установите его: python3 -m pip install --upgrade build" >&2
    exit 1
fi

python3 -m build

echo "==> Готово: dist/"
