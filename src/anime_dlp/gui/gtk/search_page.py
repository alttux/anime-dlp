import threading

from gi.repository import Adw, GLib, Gtk

from anime_dlp.core import network
from anime_dlp.core.anime_service import search_anime
from anime_dlp.labels import TYPE_MAP

DEBOUNCE_MS = 300


class SearchPage(Adw.NavigationPage):
    def __init__(self, window):
        super().__init__(title="Anime Downloader", tag="search")
        self.window = window
        self._debounce_id = None

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        if network.SUPPORTED:
            self.interface_button = Gtk.MenuButton(
                icon_name="network-wired-symbolic",
                tooltip_text=self._interface_tooltip(),
            )
            self._build_interface_popover()
            header.pack_end(self.interface_button)
        toolbar_view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Введите название аниме")
        self.search_entry.connect("search-changed", self._on_search_changed)
        box.append(self.search_entry)

        self.stack = Gtk.Stack()

        self.status_page = Adw.StatusPage(
            icon_name="system-search-symbolic",
            title="Поиск аниме",
            description="Введите название, чтобы увидеть варианты",
        )
        self.stack.add_named(self.status_page, "empty")

        self.spinner = Adw.Spinner()
        spinner_box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        spinner_box.append(self.spinner)
        self.stack.add_named(spinner_box, "loading")

        self.not_found_page = Adw.StatusPage(
            icon_name="edit-find-symbolic",
            title="Ничего не найдено",
        )
        self.stack.add_named(self.not_found_page, "not-found")

        self.results_listbox = Gtk.ListBox(css_classes=["boxed-list"])
        self.results_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_child(self.results_listbox)
        self.stack.add_named(scrolled, "results")

        self.stack.set_visible_child_name("empty")
        box.append(self.stack)

        toolbar_view.set_content(box)
        self.set_child(toolbar_view)

    def _on_search_changed(self, entry):
        if self._debounce_id is not None:
            GLib.source_remove(self._debounce_id)
            self._debounce_id = None
        text = entry.get_text().strip()
        if not text:
            self.stack.set_visible_child_name("empty")
            return
        self._debounce_id = GLib.timeout_add(DEBOUNCE_MS, self._trigger_search, text)

    def _trigger_search(self, text: str):
        self._debounce_id = None
        self.stack.set_visible_child_name("loading")
        threading.Thread(target=self._search_worker, args=(text,), daemon=True).start()
        return GLib.SOURCE_REMOVE

    def _search_worker(self, query: str):
        try:
            items = search_anime(query)
            error = None
        except Exception as exc:
            items = []
            error = str(exc)
        GLib.idle_add(self._on_search_results, query, items, error)

    def _on_search_results(self, query: str, items: list[dict], error: str | None):
        if query != self.search_entry.get_text().strip():
            return GLib.SOURCE_REMOVE

        if error:
            self.window.show_toast(f"Ошибка поиска: {error}")
            self.stack.set_visible_child_name("empty")
            return GLib.SOURCE_REMOVE

        if not items:
            self.stack.set_visible_child_name("not-found")
            return GLib.SOURCE_REMOVE

        row = self.results_listbox.get_row_at_index(0)
        while row is not None:
            self.results_listbox.remove(row)
            row = self.results_listbox.get_row_at_index(0)

        for item in items:
            raw_type = item.get("type", "")
            anime_type = TYPE_MAP.get(raw_type, raw_type)
            year = item.get("year", "")
            row = Adw.ActionRow(
                title=item.get("title", "Unknown"),
                subtitle=f"{year} · {anime_type}",
                activatable=True,
            )
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", self._on_result_activated, item)
            self.results_listbox.append(row)

        self.stack.set_visible_child_name("results")
        return GLib.SOURCE_REMOVE

    def _on_result_activated(self, row, item: dict):
        if not item.get("shikimori_id"):
            self.window.show_toast(
                "У этого аниме нет shikimori_id, скачивание невозможно"
            )
            return
        from anime_dlp.gui.gtk.details_page import DetailsPage

        self.window.push_page(DetailsPage(window=self.window, item=item))

    def _interface_tooltip(self) -> str:
        current = network.get_current_interface()
        return f"Интерфейс: {current}" if current else "Сетевой интерфейс: системный"

    def _build_interface_popover(self):
        popover = Gtk.Popover()
        listbox = Gtk.ListBox(css_classes=["boxed-list"])
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        current = network.get_current_interface()

        default_row = Adw.ActionRow(
            title="Системный (по умолчанию)", activatable=True
        )
        if current is None:
            default_row.add_suffix(Gtk.Image.new_from_icon_name("object-select-symbolic"))
        default_row.connect("activated", self._on_interface_selected, None, popover)
        listbox.append(default_row)

        for name in network.list_interfaces():
            row = Adw.ActionRow(title=name, activatable=True)
            if name == current:
                row.add_suffix(Gtk.Image.new_from_icon_name("object-select-symbolic"))
            row.connect("activated", self._on_interface_selected, name, popover)
            listbox.append(row)

        popover.set_child(listbox)
        self.interface_button.set_popover(popover)

    def _on_interface_selected(self, row, interface: str | None, popover):
        network.bind_to_interface(interface)
        popover.popdown()
        self.interface_button.set_tooltip_text(self._interface_tooltip())
        self._build_interface_popover()
