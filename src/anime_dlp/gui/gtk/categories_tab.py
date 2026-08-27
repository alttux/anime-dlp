from gi.repository import Gtk

from anime_dlp.core.anime_service import GENRES
from anime_dlp.gui.genre_posters import get_genre_poster
from anime_dlp.gui.gtk.cover_card import CoverCard


class CategoriesTab(Gtk.Box):
    """Сетка жанров. Обложки — статичные постеры, сгенерированные нейросетью
    под смысл жанра (gui/genre_posters.py), а не топ-1 аниме жанра, поэтому
    карточки собираются сразу целиком, без фоновой подгрузки."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window = window

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

        self._build_cards()

    def reload(self):
        """Пересобирает карточки (кнопка «Обновить») — постеры статичные, так
        что достаточно просто перерисовать сетку."""
        while (child := self.flow_box.get_first_child()) is not None:
            self.flow_box.remove(child)
        self._build_cards()

    def _build_cards(self):
        for genre in GENRES:
            card = CoverCard(None, on_click=self._make_click_handler(genre), title=genre)
            card.set_static_cover(get_genre_poster(genre))
            self.flow_box.append(card)

    def _make_click_handler(self, genre: str):
        # У карточки жанра нет своей записи аниме — клик открывает сетку жанра.
        def on_click(_item):
            from anime_dlp.gui.gtk.genre_page import GenrePage

            self.window.push_page(GenrePage(window=self.window, genre=genre))

        return on_click
