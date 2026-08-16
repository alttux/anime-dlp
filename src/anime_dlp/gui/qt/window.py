from pathlib import Path

from PyQt6.QtWidgets import QMainWindow, QStackedWidget

from anime_dlp.gui.qt.widgets import ToastOverlay


class AnimeDlpWindow(QMainWindow):
    def __init__(self, download_dir: Path):
        super().__init__()
        self.download_dir = download_dir

        self.resize(720, 560)
        self.setWindowTitle("Anime Downloader")

        self.nav_stack = QStackedWidget()

        self.toast_overlay = ToastOverlay()
        self.toast_overlay.set_content(self.nav_stack)
        self.setCentralWidget(self.toast_overlay)

        self._pages: list = []

        from anime_dlp.gui.qt.home_page import HomePage

        self.push_page(HomePage(window=self))

    def push_page(self, page):
        self._pages.append(page)
        self.nav_stack.addWidget(page)
        self.nav_stack.setCurrentWidget(page)

    def pop_page(self):
        if len(self._pages) <= 1:
            return
        page = self._pages.pop()
        self.nav_stack.setCurrentWidget(self._pages[-1])
        self.nav_stack.removeWidget(page)
        page.deleteLater()

    def show_toast(self, message: str):
        self.toast_overlay.show_toast(message)
