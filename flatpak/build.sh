#!/usr/bin/env bash
# Собирает Flatpak-пакет anime-dlp и кладёт готовый .flatpak в корень проекта.
# Повторяет шаги из README.md -> Установка -> Flatpak -> "Сборка Flatpak из исходников".

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="io.github.alttux.AnimeDlp"
MANIFEST="$APP_ID.yml"
OUT_FILE="$SCRIPT_DIR/../anime-dlp.flatpak"

cd "$SCRIPT_DIR"

for cmd in flatpak flatpak-builder; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Ошибка: не найдена команда '$cmd'. Установите flatpak и flatpak-builder." >&2
        exit 1
    fi
done

echo "==> Увеличение версии пакета"
python3 "$SCRIPT_DIR/../scripts/bump_version.py"

echo "==> Проверка remote flathub"
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo

echo "==> Проверка рантайма и SDK"
flatpak install --user --noninteractive flathub \
    org.gnome.Platform//49 org.gnome.Sdk//49

echo "==> Сборка и установка пакета"
flatpak-builder --force-clean --user --install --repo=repo build-dir "$MANIFEST"

echo "==> Упаковка в один .flatpak файл"
flatpak build-bundle repo "$OUT_FILE" "$APP_ID"

echo "==> Готово: $OUT_FILE"
