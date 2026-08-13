#!/usr/bin/env bash
# Генерирует AnimeDlp.icns из SVG-иконки проекта (data/icons/...svg).
# Требует rsvg-convert (brew install librsvg) и iconutil (входит в macOS).
set -euo pipefail

SRC_SVG="data/icons/io.github.alttux.AnimeDlp.svg"
ICONSET_DIR="packaging/macos/AnimeDlp.iconset"
OUT_ICNS="packaging/macos/AnimeDlp.icns"

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

for size in 16 32 128 256 512; do
  rsvg-convert -w "$size" -h "$size" "$SRC_SVG" -o "$ICONSET_DIR/icon_${size}x${size}.png"
  double=$((size * 2))
  rsvg-convert -w "$double" -h "$double" "$SRC_SVG" -o "$ICONSET_DIR/icon_${size}x${size}@2x.png"
done

iconutil -c icns "$ICONSET_DIR" -o "$OUT_ICNS"
rm -rf "$ICONSET_DIR"

echo "Готово: $OUT_ICNS"
