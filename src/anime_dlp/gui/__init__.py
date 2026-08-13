import os
import sys
from pathlib import Path


def run_gui(download_dir: Path) -> int:
    # По умолчанию: PyQt6 на Windows, GTK4/libadwaita на Linux/macOS.
    # ANIME_DLP_GUI_BACKEND=gtk|qt позволяет переопределить выбор — нужно,
    # например, для запуска GTK-версии на Windows через MSYS2 (см. WINDOWS.md).
    backend = os.environ.get("ANIME_DLP_GUI_BACKEND", "").strip().lower()
    if not backend:
        backend = "qt" if sys.platform == "win32" else "gtk"

    if backend == "qt":
        from anime_dlp.gui.qt.app import run_gui as _run_gui
    else:
        from anime_dlp.gui.gtk.app import run_gui as _run_gui
    return _run_gui(download_dir)


__all__ = ["run_gui"]
