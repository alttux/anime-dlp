import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from anime_dlp.gui.qt import workers
from anime_dlp.gui.qt.widgets import APP_STYLESHEET
from anime_dlp.gui.qt.window import AnimeDlpWindow


def run_gui(download_dir: Path) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Anime Downloader")
    app.setStyleSheet(APP_STYLESHEET)

    window = AnimeDlpWindow(download_dir)
    window.show()
    # Фоновые воркеры (search/info/poster/download) крутят блокирующий сетевой
    # I/O в QThread.run() без цикла событий — на выходе их надо принудительно
    # остановить, иначе Qt делает abort() на недоработавшем QThread.
    app.aboutToQuit.connect(workers.stop_all_workers)

    return app.exec()
