#!/usr/bin/env bash
# Генерирует AnimeDlp.ico (мультиразрешение) из SVG-иконки проекта
# (data/icons/...svg). Требует rsvg-convert (apt/pacman/brew install
# librsvg) и Pillow (pip install pillow). Запускать из корня репозитория.
set -euo pipefail

SRC_SVG="data/icons/io.github.alttux.AnimeDlp.svg"
PNG_DIR="packaging/windows/.ico_pngs"
OUT_ICO="packaging/windows/AnimeDlp.ico"

rm -rf "$PNG_DIR"
mkdir -p "$PNG_DIR"

for size in 16 32 48 256; do
  rsvg-convert -w "$size" -h "$size" "$SRC_SVG" -o "$PNG_DIR/icon_${size}.png"
done

python3 - "$PNG_DIR" "$OUT_ICO" <<'PYEOF'
import sys
from PIL import Image

png_dir, out_ico = sys.argv[1], sys.argv[2]
sizes = [16, 32, 48, 256]
base = Image.open(f"{png_dir}/icon_256.png")
base.save(
    out_ico,
    format="ICO",
    sizes=[(s, s) for s in sizes],
)
PYEOF

rm -rf "$PNG_DIR"

echo "Готово: $OUT_ICO"
