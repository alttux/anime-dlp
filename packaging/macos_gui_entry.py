"""Точка входа для macOS .app-бандла (PyInstaller, --windowed).

При двойном клике по .app пользователь не передаёт аргументы командной
строки и не имеет терминала для CLI-диалога, поэтому здесь сразу
запускается GUI — в отличие от обычной точки входа `anime_dlp.main`,
которая по умолчанию ведёт себя как CLI и ждёт `--gui` явным флагом.

Переменные окружения для GTK4/libadwaita (typelib'ы, схемы GSettings,
темы иконок) выставляются здесь же, до `import gi`, потому что внутри
бандла они лежат не в системных путях Homebrew, а в `sys._MEIPASS`
(см. packaging/macos/build.sh, флаги --add-data).
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

from anime_dlp.config import DOWNLOAD_DIR
from anime_dlp.gui import run_gui

if __name__ == "__main__":
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    sys.exit(run_gui(DOWNLOAD_DIR))
