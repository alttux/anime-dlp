#!/usr/bin/env bash
# Создаёт .dmg-установщик с .app-бандлом и ссылкой на /Applications.
set -euo pipefail

APP_PATH="${1:?Укажите путь к .app}"
VOL_NAME="${2:-AnimeDlp}"
DMG_PATH="${3:-dist/AnimeDlp_macos_universal.dmg}"

echo "=== Сборка DMG: $DMG_PATH ==="
echo "  Приложение: $APP_PATH"
echo "  Имя тома:   $VOL_NAME"

DMG_STAGING="$(mktemp -d)"
trap 'rm -rf "$DMG_STAGING"' EXIT

mkdir -p "$DMG_STAGING"
cp -R "$APP_PATH" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

mkdir -p "$(dirname "$DMG_PATH")"
rm -f "$DMG_PATH"

hdiutil create \
  -volname "$VOL_NAME" \
  -srcfolder "$DMG_STAGING" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "=== DMG успешно создан: $DMG_PATH ==="
