import threading

from gi.repository import Adw, GLib, Gtk

from anime_dlp.core.anime_service import get_popular_anime
from anime_dlp.gui import prefetch
from anime_dlp.gui.gtk.cover_card import CoverCard

# Насколько близко к концу прокрутки нужно оказаться, чтобы подгрузить
# следующую пачку (в тех же единицах, что и Gtk.Adjustment, обычно пиксели).
_SCROLL_THRESHOLD = 200


class CatalogTab(Gtk.Box):
    """Сетка обложек с бесконечной прокруткой. loader — источник страниц с
    сигнатурой (cursor, limit) -> (items, next_cursor); по умолчанию это
    популярное («Главное»), страница жанра передаёт сюда get_genre_anime."""

    PAGE_SIZE = 10

    def __init__(self, window, loader=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window = window
        self._loader = loader or get_popular_anime
        self._next_cursor: str | None = None
        self._loading = False
        # Растёт при reload(): ответы запросов, стартовавших до перезагрузки,
        # игнорируются, иначе они дорисовали бы старые карточки в новую сетку.
        self._generation = 0

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
        self.scrolled = Gtk.ScrolledWindow(vexpand=True)
        self.scrolled.set_child(self.flow_box)
        self.append(self.scrolled)

        adjustment = self.scrolled.get_vadjustment()
        # "changed" срабатывает, когда меняется высота содержимого или
        # видимой области (добавили карточки, изменили размер окна) —
        # этим же обработчиком дозаполняем сетку под видимую область.
        adjustment.connect("changed", lambda *_: self._maybe_load_more())
        adjustment.connect("value-changed", lambda *_: self._maybe_load_more())

        self.spinner = Adw.Spinner(halign=Gtk.Align.CENTER, margin_bottom=12)
        self.spinner.set_visible(False)
        self.append(self.spinner)

        self._load_page()

    def reload(self):
        """Полная перезагрузка сетки с первой страницы (кнопка «Обновить»)."""
        self._generation += 1
        self._loading = False
        self._next_cursor = None
        while (child := self.flow_box.get_first_child()) is not None:
            self.flow_box.remove(child)
        self._load_page()

    def _load_page(self):
        if self._loading:
            return
        self._loading = True
        self.spinner.set_visible(True)
        threading.Thread(
            target=self._load_worker,
            args=(self._next_cursor, self._generation),
            daemon=True,
        ).start()

    def _load_worker(self, cursor: str | None, generation: int):
        try:
            items, next_cursor = self._loader(cursor, self.PAGE_SIZE)
            error = None
        except Exception as exc:
            items, next_cursor, error = [], cursor, str(exc)
        GLib.idle_add(self._on_page_loaded, items, next_cursor, error, generation)

    def _on_page_loaded(
        self,
        items: list[dict],
        next_cursor: str | None,
        error: str | None,
        generation: int,
    ):
        if generation != self._generation:
            return GLib.SOURCE_REMOVE
        self._loading = False
        self.spinner.set_visible(False)
        if error:
            self.window.show_toast(f"Ошибка загрузки: {error}")
        else:
            for item in items:
                self.flow_box.append(CoverCard(item, on_click=self._on_card_clicked))
                prefetch.prefetch(item.get("shikimori_id"))
            self._next_cursor = next_cursor
        return GLib.SOURCE_REMOVE

    def _maybe_load_more(self):
        if self._loading or self._next_cursor is None:
            return
        adjustment = self.scrolled.get_vadjustment()
        near_bottom = (
            adjustment.get_value() + adjustment.get_page_size()
            >= adjustment.get_upper() - _SCROLL_THRESHOLD
        )
        not_full = adjustment.get_upper() <= adjustment.get_page_size() + 1
        if near_bottom or not_full:
            self._load_page()

    def _on_card_clicked(self, item: dict):
        if not item.get("shikimori_id"):
            self.window.show_toast(
                "У этого аниме нет shikimori_id, скачивание невозможно"
            )
            return
        from anime_dlp.gui.gtk.details_page import DetailsPage

        self.window.push_page(DetailsPage(window=self.window, item=item))
