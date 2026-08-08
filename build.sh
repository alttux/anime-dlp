#!/usr/bin/env bash
# Собирает Python-пакет (wheel + sdist) в dist/. Перед сборкой увеличивает
# patch-версию в pyproject.toml на 1 (см. scripts/bump_version.py), чтобы
# каждая сборка получала новую версию.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! python3 -c "import build" >/dev/null 2>&1; then
    echo "Ошибка: не найден модуль 'build'. Установите его: python3 -m pip install --upgrade build" >&2
    exit 1
fi

python3 scripts/bump_version.py

python3 -m build

echo "==> Готово: dist/"
