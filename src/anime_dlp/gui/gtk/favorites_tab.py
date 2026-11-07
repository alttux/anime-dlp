from gi.repository import Adw, Gtk

from anime_dlp.core import favorites, watch_history
from anime_dlp.gui.gtk.cover_card import CoverCard

_STATUS_ICONS = {
    watch_history.STATUS_WATCHED: "object-select-symbolic",
    watch_history.STATUS_IN_PROGRESS: "media-playback-start-symbolic",
    watch_history.STATUS_NOT_STARTED: "starred-symbolic",
}


def _create_section_header(title: str, count: int, icon_name: str) -> Gtk.Box:
    """Заголовок группы в стиле файловых менеджеров (иконка, название, счётчик и разделитель)."""
    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    header.set_margin_top(14)
    header.set_margin_bottom(8)
    header.set_margin_start(16)
    header.set_margin_end(16)

    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.add_css_class("dim-label")

    title_label = Gtk.Label(label=title, css_classes=["heading"])
    count_label = Gtk.Label(label=f"({count})", css_classes=["dim-label"])
    separator = Gtk.Separator(
        orientation=Gtk.Orientation.HORIZONTAL,
        hexpand=True,
        valign=Gtk.Align.CENTER,
    )

    header.append(icon)
    header.append(title_label)
    header.append(count_label)
    header.append(separator)
    return header


def _create_flow_box() -> Gtk.FlowBox:
    return Gtk.FlowBox(
        selection_mode=Gtk.SelectionMode.NONE,
        homogeneous=True,
        column_spacing=16,
        row_spacing=16,
        min_children_per_line=1,
        max_children_per_line=8,
        valign=Gtk.Align.START,
        halign=Gtk.Align.FILL,
        hexpand=True,
        margin_start=12,
        margin_end=12,
        margin_bottom=14,
    )


class FavoritesTab(Gtk.Box):
    """Сетка аниме, отмеченных звёздочкой, сгруппированная по статусу просмотра
    (Просмотрено / Начато / Не начато) аналогично файловым менеджерам."""

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

        self.groups_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_child(self.groups_box)
        self.stack.add_named(scrolled, "items")

        self.append(self.stack)
        self.connect("map", lambda *_: self.reload())
        self.reload()

    def reload(self):
        """Перечитывает избранное с диска, группирует по статусу просмотра
        (Просмотрено / Начато / Не начато) и перестраивает интерфейс."""
        while (child := self.groups_box.get_first_child()) is not None:
            self.groups_box.remove(child)

        items = favorites.load()
        if not items:
            self.stack.set_visible_child_name("empty")
            return

        grouped: dict[str, list[dict]] = {
            watch_history.STATUS_WATCHED: [],
            watch_history.STATUS_IN_PROGRESS: [],
            watch_history.STATUS_NOT_STARTED: [],
        }

        for item in items:
            status = watch_history.get_watch_status(item)
            grouped[status].append(item)

        has_any_items = False
        for status in watch_history.WATCH_STATUS_ORDER:
            group_items = grouped.get(status, [])
            if not group_items:
                continue

            has_any_items = True
            icon_name = _STATUS_ICONS.get(status, "view-list-symbolic")
            header = _create_section_header(status, len(group_items), icon_name)
            self.groups_box.append(header)

            flow_box = _create_flow_box()
            for item in group_items:
                flow_box.append(CoverCard(item, on_click=self._on_card_clicked))
            self.groups_box.append(flow_box)

        self.stack.set_visible_child_name("items" if has_any_items else "empty")

    def _on_card_clicked(self, item: dict):
        from anime_dlp.gui.gtk.details_page import DetailsPage

        self.window.push_page(DetailsPage(window=self.window, item=item))
