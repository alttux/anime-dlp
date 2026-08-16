from pathlib import Path

from gi.repository import Adw

from anime_dlp.gui.gtk.home_page import HomePage


class AnimeDlpWindow(Adw.ApplicationWindow):
    def __init__(self, application, download_dir: Path):
        super().__init__(application=application)
        self.download_dir = download_dir

        self.set_default_size(720, 560)
        self.set_title("Anime Downloader")

        self.nav_view = Adw.NavigationView()
        self.nav_view.add(HomePage(window=self))

        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(self.nav_view)

        self.set_content(self.toast_overlay)

    def push_page(self, page):
        self.nav_view.push(page)

    def pop_page(self):
        self.nav_view.pop()

    def show_toast(self, message: str):
        self.toast_overlay.add_toast(Adw.Toast.new(message))
