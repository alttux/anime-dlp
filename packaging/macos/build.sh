#!/usr/bin/env bash
# Собирает dist/AnimeDlp.app через PyInstaller: GUI-бандл с GTK4/libadwaita,
# установленными через Homebrew. Запускать из корня репозитория, внутри
# venv с --system-site-packages (см. .github/workflows/macos-build.yml).
set -euo pipefail

APP_NAME="AnimeDlp"
BREW_PREFIX="$(brew --prefix)"

export GI_TYPELIB_PATH="$BREW_PREFIX/lib/girepository-1.0"
export DYLD_LIBRARY_PATH="$BREW_PREFIX/lib:${DYLD_LIBRARY_PATH:-}"
export PKG_CONFIG_PATH="$BREW_PREFIX/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export XDG_DATA_DIRS="$BREW_PREFIX/share:${XDG_DATA_DIRS:-}"

echo "=== DEBUG: GI_TYPELIB_PATH=$GI_TYPELIB_PATH ==="
echo "=== DEBUG: Homebrew prefix: $BREW_PREFIX ==="

# GStreamer для онлайн-плеера (player_page.py). PyInstaller не видит его
# зависимостей через Python-импорты: библиотеки, плагины и scanner
# добавляем явно. Плагины кладутся в gst_plugins/, scanner — в gst_libexec/;
# пути в бандле выставляет packaging/macos_gui_entry.py.
GST_PREFIX="$BREW_PREFIX/opt/gstreamer"
GST_BUNDLE_ARGS=()
for lib in "$GST_PREFIX"/lib/libgst*.dylib; do
  GST_BUNDLE_ARGS+=(--add-binary "$lib:.")
done
for plugin in "$GST_PREFIX"/lib/gstreamer-1.0/*.dylib; do
  GST_BUNDLE_ARGS+=(--add-binary "$plugin:gst_plugins")
done
GST_BUNDLE_ARGS+=(--add-binary "$GST_PREFIX/libexec/gstreamer-1.0/gst-plugin-scanner:gst_libexec")
echo "=== DEBUG: GStreamer bundle args: ${#GST_BUNDLE_ARGS[@]} ==="

rm -rf build dist "${APP_NAME}.spec"

pyinstaller \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --icon packaging/macos/AnimeDlp.icns \
  --collect-all anime_parsers_ru \
  --copy-metadata anime-dlp \
  --hidden-import gi \
  --add-data "$GI_TYPELIB_PATH:gi_typelibs" \
  --add-data "$BREW_PREFIX/share/glib-2.0/schemas:share/glib-2.0/schemas" \
  --add-data "$BREW_PREFIX/share/icons/Adwaita:share/icons/Adwaita" \
  --add-data "$BREW_PREFIX/share/icons/hicolor:share/icons/hicolor" \
  --add-data "src/anime_dlp/gui/assets/genre_posters:anime_dlp/gui/assets/genre_posters" \
  "${GST_BUNDLE_ARGS[@]}" \
  packaging/macos_gui_entry.py

echo "=== DEBUG: Build finished, dist/${APP_NAME}.app ==="
