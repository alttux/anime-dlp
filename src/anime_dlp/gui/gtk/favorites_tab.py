from gi.repository import Adw, Gtk

from anime_dlp.core import favorites
from anime_dlp.gui.gtk.cover_card import CoverCard


class FavoritesTab(Gtk.Box):
    """Сетка аниме, отмеченных звёздочкой на странице аниме. Данные лежат на
    диске полными записями, поэтому вкладка рисуется без единого запроса."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window = window

        self.stack = Gtk.Stack(vexpand=True)

        self.status_page = Adw.StatusPage(
            icon_name="starred-symbolic",
            title="Избранное пусто",
            description="Отмечайте аниме звёздочкой на странице аниме",
        )
        self.stack.add_named(self.status_page, "empty")

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
        self.stack.add_named(scrolled, "items")

        self.append(self.stack)
        self.reload()

    def reload(self):
        """Перечитывает избранное с диска и перестраивает сетку. Вызывается
        при каждом показе вкладки — звёздочку могли поставить только что."""
        while (child := self.flow_box.get_first_child()) is not None:
            self.flow_box.remove(child)

        items = favorites.load()
        for item in items:
            self.flow_box.append(CoverCard(item, on_click=self._on_card_clicked))

        self.stack.set_visible_child_name("items" if items else "empty")

    def _on_card_clicked(self, item: dict):
        from anime_dlp.gui.gtk.details_page import DetailsPage

        self.window.push_page(DetailsPage(window=self.window, item=item))
