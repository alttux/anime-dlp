import sys
from pathlib import Path

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from anime_dlp.gui.qt.widgets import APP_STYLESHEET
from anime_dlp.gui.qt.window import AnimeDlpWindow


def _stop_running_threads(window: AnimeDlpWindow):
    # Background workers (search/info/poster/download) run blocking network
    # I/O in QThread.run() with no event loop, so they can't be asked to
    # quit gracefully — force-stop any still running so Qt doesn't abort
    # the process on exit with unfinished QThreads.
    for thread in window.findChildren(QThread):
        if thread.isRunning():
            thread.terminate()
            thread.wait()


def run_gui(download_dir: Path) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Anime Downloader")
    app.setStyleSheet(APP_STYLESHEET)

    window = AnimeDlpWindow(download_dir)
    window.show()
    app.aboutToQuit.connect(lambda: _stop_running_threads(window))

    return app.exec()
