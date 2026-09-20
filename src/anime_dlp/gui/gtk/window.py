from pathlib import Path

from gi.repository import Adw

from anime_dlp.gui.formatting import APP_TITLE
from anime_dlp.gui.gtk.home_page import HomePage


class AnimeDlpWindow(Adw.ApplicationWindow):
    def __init__(self, application, download_dir: Path):
        super().__init__(application=application)
        self.download_dir = download_dir

        self.set_default_size(720, 560)
        self.set_title(APP_TITLE)

        self.nav_view = Adw.NavigationView()
        home_page = HomePage(window=self)
        self.nav_view.add(home_page)
        self._visible_page = home_page
        self.nav_view.connect("notify::visible-page", self._on_visible_page_changed)

        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(self.nav_view)

        self.set_content(self.toast_overlay)

    def push_page(self, page):
        self.nav_view.push(page)

    def pop_page(self):
        self.nav_view.pop()

    def _on_visible_page_changed(self, nav_view, _pspec):
        visible_page = nav_view.get_visible_page()
        previous_page = self._visible_page
        self._visible_page = visible_page
        if previous_page is visible_page:
            return
        cleanup = getattr(previous_page, "cleanup", None)
        if cleanup is not None:
            cleanup()

    def show_toast(self, message: str):
        self.toast_overlay.add_toast(Adw.Toast.new(message))
