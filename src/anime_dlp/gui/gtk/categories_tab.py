import threading

from gi.repository import Adw, GLib, Gtk

from anime_dlp.core.anime_service import GENRES, get_genre_cover
from anime_dlp.gui.gtk.cover_card import CoverCard


class CategoriesTab(Gtk.Box):
    """Сетка жанров. Карточки создаются сразу все и в фиксированном порядке —
    так лэйаут не прыгает, — а обложки (топ-1 аниме жанра) подставляются в них
    по мере готовности фоновой загрузки."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window = window
        self._generation = 0
        self._cards: dict[str, CoverCard] = {}

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

        self.spinner = Adw.Spinner(halign=Gtk.Align.CENTER, margin_bottom=12)
        self.spinner.set_visible(False)
        self.append(self.spinner)

        self._build_cards()

    def reload(self):
        """Пересобирает карточки и заново ищет обложки (кнопка «Обновить»)."""
        self._generation += 1
        while (child := self.flow_box.get_first_child()) is not None:
            self.flow_box.remove(child)
        self._build_cards()

    def _build_cards(self):
        self._cards = {}
        for genre in GENRES:
            card = CoverCard(None, on_click=self._make_click_handler(genre), title=genre)
            self._cards[genre] = card
            self.flow_box.append(card)

        self.spinner.set_visible(True)
        threading.Thread(
            target=self._load_covers_worker, args=(self._generation,), daemon=True
        ).start()

    def _load_covers_worker(self, generation: int):
        used_ids: set[str] = set()
        for genre in GENRES:
            try:
                item = get_genre_cover(genre, used_ids)
            except Exception:
                continue
            if item:
                used_ids.add(item.get("shikimori_id"))
                GLib.idle_add(self._on_cover_loaded, genre, item, generation)
        GLib.idle_add(self._on_covers_done, generation)

    def _on_cover_loaded(self, genre: str, item: dict, generation: int):
        if generation != self._generation:
            return GLib.SOURCE_REMOVE
        card = self._cards.get(genre)
        if card is not None:
            card.set_item(item)
        return GLib.SOURCE_REMOVE

    def _on_covers_done(self, generation: int):
        if generation == self._generation:
            self.spinner.set_visible(False)
        return GLib.SOURCE_REMOVE

    def _make_click_handler(self, genre: str):
        # У карточки жанра нет своей записи аниме — клик открывает сетку жанра.
        def on_click(_item):
            from anime_dlp.gui.gtk.genre_page import GenrePage

            self.window.push_page(GenrePage(window=self.window, genre=genre))

        return on_click
