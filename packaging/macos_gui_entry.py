"""Точка входа для macOS .app-бандла (PyInstaller, --windowed).

При двойном клике по .app пользователь не передаёт аргументы командной
строки и не имеет терминала для CLI-диалога, поэтому здесь сразу
запускается GUI — в отличие от обычной точки входа `anime_dlp.main`,
которая по умолчанию ведёт себя как CLI и ждёт `--gui` явным флагом.

Переменные окружения для GTK4/libadwaita (typelib'ы, схемы GSettings,
темы иконок) и GStreamer (плагины, scanner) выставляются здесь же, до
`import gi`, потому что внутри бандла они лежат не в системных путях
Homebrew, а в `sys._MEIPASS` (см. packaging/macos/build.sh, флаги
--add-data и --add-binary).
"""

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    bundle_resources = Path(sys._MEIPASS)
    os.environ["GI_TYPELIB_PATH"] = str(bundle_resources / "gi_typelibs")
    os.environ["XDG_DATA_DIRS"] = (
        str(bundle_resources / "share") + os.pathsep + os.environ.get("XDG_DATA_DIRS", "")
    )
    os.environ["GSETTINGS_SCHEMA_DIR"] = str(
        bundle_resources / "share" / "glib-2.0" / "schemas"
    )
    # Только плагины из бандла: системные из Homebrew в .app не нужны и
    # могут не совпасть по версии с библиотеками внутри бандла.
    os.environ["GST_PLUGIN_SYSTEM_PATH"] = str(bundle_resources / "gst_plugins")
    os.environ["GST_PLUGIN_SCANNER"] = str(
        bundle_resources / "gst_libexec" / "gst-plugin-scanner"
    )

from anime_dlp.config import DOWNLOAD_DIR
from anime_dlp.gui import run_gui

if __name__ == "__main__":
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    sys.exit(run_gui(DOWNLOAD_DIR))
