"""Точка входа для Windows GUI-бандла (PyInstaller, --windowed).

При двойном клике по .exe пользователь не передаёт аргументы командной
строки и не имеет консоли для CLI-диалога, поэтому здесь сразу запускается
GUI на PyQt6 — в отличие от обычной точки входа `anime_dlp.main`, которая
по умолчанию ведёт себя как CLI и ждёт `--gui` явным флагом.

В отличие от macOS-сборки на GTK4/libadwaita (packaging/macos_gui_entry.py),
здесь не нужно выставлять переменные окружения для typelib'ов/схем/тем —
PyQt6 поставляется в виде самодостаточного wheel с уже забандленными
бинарниками Qt, и PyInstaller подхватывает их автоматически.
"""

import sys

from anime_dlp.config import DOWNLOAD_DIR
from anime_dlp.gui.qt.app import run_gui

if __name__ == "__main__":
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    sys.exit(run_gui(DOWNLOAD_DIR))
