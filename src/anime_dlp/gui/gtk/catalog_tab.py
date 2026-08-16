import threading

from gi.repository import Adw, GLib, Gtk

from anime_dlp.core.anime_service import get_popular_anime
from anime_dlp.gui.gtk.cover_card import CoverCard


class CatalogTab(Gtk.Box):
    PAGE_SIZE = 10

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window = window
        self._next_cursor: str | None = None
        self._loading = False

        self.flow_box = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=True,
            column_spacing=16,
            row_spacing=16,
            min_children_per_line=1,
            max_children_per_line=8,
            valign=Gtk.Align.START,
            halign=Gtk.Align.FILL,
            hexpand=True,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_child(self.flow_box)
        self.append(scrolled)

        self.load_more_button = Gtk.Button(
            label="Прогрузить ещё", halign=Gtk.Align.CENTER, margin_bottom=12
        )
        self.load_more_button.connect("clicked", lambda *_: self._load_page())
        self.append(self.load_more_button)

        self.spinner = Adw.Spinner(halign=Gtk.Align.CENTER, margin_bottom=12)
        self.spinner.set_visible(False)
        self.append(self.spinner)

        self._load_page()

    def _load_page(self):
        if self._loading:
            return
        self._loading = True
        self.load_more_button.set_sensitive(False)
        self.spinner.set_visible(True)
        threading.Thread(target=self._load_worker, args=(self._next_cursor,), daemon=True).start()

    def _load_worker(self, cursor: str | None):
        try:
            items, next_cursor = get_popular_anime(cursor=cursor, limit=self.PAGE_SIZE)
            error = None
        except Exception as exc:
            items, next_cursor, error = [], cursor, str(exc)
        GLib.idle_add(self._on_page_loaded, items, next_cursor, error)

    def _on_page_loaded(self, items: list[dict], next_cursor: str | None, error: str | None):
        self._loading = False
        self.spinner.set_visible(False)
        if error:
            self.window.show_toast(f"Ошибка загрузки: {error}")
        else:
            for item in items:
                self.flow_box.append(CoverCard(item, on_click=self._on_card_clicked))
            self._next_cursor = next_cursor
        self.load_more_button.set_sensitive(True)
        self.load_more_button.set_visible(next_cursor is not None)
        return GLib.SOURCE_REMOVE

    def _on_card_clicked(self, item: dict):
        if not item.get("shikimori_id"):
            self.window.show_toast(
                "У этого аниме нет shikimori_id, скачивание невозможно"
            )
            return
        from anime_dlp.gui.gtk.details_page import DetailsPage

        self.window.push_page(DetailsPage(window=self.window, item=item))
