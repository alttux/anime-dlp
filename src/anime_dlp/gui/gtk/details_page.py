import threading

import requests
from gi.repository import Adw, Gdk, GLib, Gtk

from anime_dlp.core import favorites
from anime_dlp.core.anime_info import AnimeInfo, build_detail_rows, extract_anime_info
from anime_dlp.core.cache import fetch_image_cached
from anime_dlp.gui import prefetch


class DetailsPage(Adw.NavigationPage):
    def __init__(self, window, item: dict):
        super().__init__(title=item.get("title", "Anime"), tag="details")
        self.window = window
        self.item = item
        self.translations = []
        self.series_count = None
        self.is_movie = False
        self.episode_checks: dict[int, Gtk.CheckButton] = {}
        self._syncing_select_all = False
        self._syncing_favorite = False

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        self.stack = Gtk.Stack(hexpand=True)

        spinner_box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        spinner_box.append(Adw.Spinner())
        self.stack.add_named(spinner_box, "loading")

        self.form_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=18, hexpand=True
        )
        self.form_box.set_margin_top(18)
        self.form_box.set_margin_bottom(18)
        self.form_box.set_margin_start(18)
        self.form_box.set_margin_end(18)

        form_scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        form_scrolled.set_child(self.form_box)
        self.stack.add_named(form_scrolled, "form")

        self.poster_picture = Gtk.Picture(
            content_fit=Gtk.ContentFit.COVER,
            can_shrink=True,
            halign=Gtk.Align.START,
            valign=Gtk.Align.START,
            css_classes=["rounded-poster"],
        )
        self.poster_picture.set_overflow(Gtk.Overflow.HIDDEN)
        self.poster_picture.set_size_request(200, 280)
        self.poster_picture.set_visible(False)

        self.stack.set_visible_child_name("loading")

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        content_box.append(self.stack)
        content_box.set_vexpand(True)

        self.action_bar = Gtk.ActionBar()
        self.download_button = Gtk.Button(
            label="Скачать", css_classes=["suggested-action", "pill"]
        )
        self.download_button.connect("clicked", self._on_download_clicked)
        self.action_bar.pack_end(self.download_button)
        content_box.append(self.action_bar)

        toolbar_view.set_content(content_box)
        self.set_child(toolbar_view)

        threading.Thread(target=self._fetch_info_worker, daemon=True).start()

        poster_url = extract_anime_info(self.item).poster_url
        if poster_url:
            threading.Thread(
                target=self._fetch_poster_worker, args=(poster_url,), daemon=True
            ).start()

    def _fetch_poster_worker(self, poster_url: str):
        try:
            data = fetch_image_cached(poster_url, timeout=10)
        except requests.RequestException:
            return
        GLib.idle_add(self._on_poster_loaded, data)

    def _on_poster_loaded(self, data: bytes):
        try:
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
        except GLib.Error:
            return GLib.SOURCE_REMOVE
        self.poster_picture.set_paintable(texture)
        self.poster_picture.set_visible(True)
        return GLib.SOURCE_REMOVE

    def _fetch_info_worker(self):
        try:
            info = prefetch.get_or_fetch(self.item["shikimori_id"])
            error = None
        except Exception as exc:
            info = None
            error = str(exc)
        GLib.idle_add(self._on_info_loaded, info, error)

    def _on_info_loaded(self, info: dict | None, error: str | None):
        if error or not info:
            self.window.show_toast(f"Ошибка получения информации: {error}")
            self.window.pop_page()
            return GLib.SOURCE_REMOVE

        self.translations = info["translations"]
        self.series_count = info["series_count"]
        self._build_form()
        self.stack.set_visible_child_name("form")
        return GLib.SOURCE_REMOVE

    def _build_form(self):
        info = extract_anime_info(self.item)

        self.form_box.append(self._build_header(info))

        if info.description:
            description_label = Gtk.Label(
                label=info.description,
                wrap=True,
                xalign=0,
                hexpand=True,
            )
            self.form_box.append(description_label)

        translation_group = Adw.PreferencesGroup(title="Озвучка")
        self.translation_combo = Adw.ComboRow(title="Вариант озвучки")
        model = Gtk.StringList()
        for t in self.translations:
            model.append(f"{t['type']} — {t['name']}")
        self.translation_combo.set_model(model)
        # Adw.ComboRow по умолчанию обрезает (ellipsize) текст пунктов
        # выпадающего списка фиксированной шириной независимо от ширины
        # popover — своя list-factory без ellipsize показывает названия
        # озвучек/студий полностью.
        list_factory = Gtk.SignalListItemFactory()
        list_factory.connect("setup", self._on_translation_item_setup)
        list_factory.connect("bind", self._on_translation_item_bind)
        self.translation_combo.set_list_factory(list_factory)
        self.translation_combo.connect("notify::selected", self._on_translation_changed)
        translation_group.add(self.translation_combo)
        self.form_box.append(translation_group)

        self.is_movie = self.series_count == 0 or self.series_count is None

        episodes_group = Adw.PreferencesGroup(title="Серии")
        if self.is_movie:
            row = Adw.ActionRow(title="Фильм", subtitle="Определено как фильм")
            episodes_group.add(row)
        else:
            episodes_group.add(self._build_episode_checklist(info))

        self.form_box.append(episodes_group)

        self._apply_series_range()

    def _build_header(self, info: AnimeInfo) -> Gtk.Box:
        title_label = Gtk.Label(
            label=self.item.get("title", "Anime"),
            wrap=True,
            xalign=0,
            hexpand=True,
            css_classes=["title-1"],
        )

        self.favorite_button = Gtk.ToggleButton(
            active=favorites.is_favorite(self.item.get("shikimori_id")),
            valign=Gtk.Align.CENTER,
            css_classes=["flat", "circular"],
        )
        self._sync_favorite_button()
        self.favorite_button.connect("toggled", self._on_favorite_toggled)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, hexpand=True)
        title_row.append(title_label)
        title_row.append(self.favorite_button)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True)
        text_box.append(title_row)

        if info.title_orig:
            subtitle_label = Gtk.Label(
                label=info.title_orig,
                wrap=True,
                xalign=0,
                css_classes=["dim-label"],
            )
            text_box.append(subtitle_label)

        pills = self._build_genre_pills(info.genres)
        if pills is not None:
            text_box.append(pills)

        key_value_block = self._build_key_value_block(info)
        if key_value_block is not None:
            text_box.append(key_value_block)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18, hexpand=True)
        header_box.append(self.poster_picture)
        header_box.append(text_box)
        return header_box

    def _sync_favorite_button(self):
        is_favorite = self.favorite_button.get_active()
        self.favorite_button.set_icon_name(
            "starred-symbolic" if is_favorite else "non-starred-symbolic"
        )
        self.favorite_button.set_tooltip_text(
            "Убрать из избранного" if is_favorite else "Добавить в избранное"
        )

    def _on_favorite_toggled(self, button):
        # Кнопка уже переключилась визуально — приводим хранилище в то же
        # состояние (toggle() сам решает, добавить или удалить). Флаг нужен
        # потому, что set_active() ниже сам эмитит "toggled".
        if self._syncing_favorite:
            return
        self._syncing_favorite = True
        is_favorite = favorites.toggle(self.item)
        button.set_active(is_favorite)
        self._sync_favorite_button()
        self._syncing_favorite = False
        self.window.show_toast(
            "Добавлено в избранное" if is_favorite else "Удалено из избранного"
        )

    @staticmethod
    def _build_genre_pills(genres: list[str]) -> Gtk.FlowBox | None:
        if not genres:
            return None
        flow_box = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=False,
            column_spacing=6,
            row_spacing=6,
            min_children_per_line=1,
            halign=Gtk.Align.START,
        )
        for genre in genres:
            flow_box.append(Gtk.Label(label=genre, css_classes=["pill-badge"]))
        return flow_box

    @staticmethod
    def _build_key_value_block(info: AnimeInfo) -> Gtk.Grid | None:
        rows = build_detail_rows(info)
        if not rows:
            return None

        grid = Gtk.Grid(row_spacing=6, column_spacing=12, hexpand=True)
        for row_index, (label, value) in enumerate(rows):
            grid.attach(
                Gtk.Label(label=label, xalign=0, css_classes=["dim-label"]),
                0, row_index, 1, 1,
            )
            grid.attach(
                Gtk.Label(label=value, xalign=0, wrap=True, hexpand=True),
                1, row_index, 1, 1,
            )
        return grid

    def _build_episode_checklist(self, info: AnimeInfo) -> Gtk.Box:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self.select_all_check = Gtk.CheckButton(label="Выбрать все")
        self.select_all_check.connect("toggled", self._on_select_all_toggled)
        container.append(self.select_all_check)

        self.episode_checks = {}
        listbox = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        for n in range(1, self.series_count + 1):
            check = Gtk.CheckButton()
            check.connect("toggled", self._on_episode_check_toggled)
            self.episode_checks[n] = check

            row = Adw.ActionRow(title=f"Серия {n}")
            row.add_prefix(check)
            row.set_activatable_widget(check)
            if info.duration:
                row.add_suffix(Gtk.Label(label=f"~{info.duration} мин", css_classes=["dim-label"]))
            listbox.append(row)

        scrolled = Gtk.ScrolledWindow(min_content_height=300, hexpand=True, vexpand=False)
        scrolled.set_child(listbox)
        container.append(scrolled)
        return container

    def _on_select_all_toggled(self, button):
        if self._syncing_select_all:
            return
        self._syncing_select_all = True
        active = button.get_active()
        for check in self.episode_checks.values():
            if check.get_sensitive():
                check.set_active(active)
        self._syncing_select_all = False

    def _on_episode_check_toggled(self, button):
        if self._syncing_select_all:
            return
        self._sync_select_all_state()

    def _sync_select_all_state(self):
        selectable = [c for c in self.episode_checks.values() if c.get_sensitive()]
        checked = [c for c in selectable if c.get_active()]
        self._syncing_select_all = True
        if not selectable or not checked:
            self.select_all_check.set_active(False)
            self.select_all_check.set_inconsistent(False)
        elif len(checked) == len(selectable):
            self.select_all_check.set_inconsistent(False)
            self.select_all_check.set_active(True)
        else:
            self.select_all_check.set_inconsistent(True)
        self._syncing_select_all = False

    @staticmethod
    def _on_translation_item_setup(factory, list_item):
        list_item.set_child(Gtk.Label(xalign=0, margin_start=6, margin_end=6, margin_top=6, margin_bottom=6))

    @staticmethod
    def _on_translation_item_bind(factory, list_item):
        label = list_item.get_child()
        label.set_label(list_item.get_item().get_string())

    def _on_translation_changed(self, combo_row, _pspec):
        self._apply_series_range()

    def _apply_series_range(self):
        if self.is_movie or not self.translations or not self.episode_checks:
            return
        selected = self.translation_combo.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION:
            return
        first, last = self.translations[selected].get("series_range", (1, self.series_count))
        for n, check in self.episode_checks.items():
            in_range = first <= n <= last
            check.set_sensitive(in_range)
            if not in_range and check.get_active():
                check.set_active(False)
        self._sync_select_all_state()

    def _on_download_clicked(self, button):
        selected = self.translation_combo.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION or not self.translations:
            self.window.show_toast("Выберите озвучку")
            return
        translation = self.translations[selected]

        if self.is_movie:
            eps_to_download = [0]
        else:
            eps_to_download = sorted(
                n for n, check in self.episode_checks.items() if check.get_active()
            )
            if not eps_to_download:
                self.window.show_toast("Выберите хотя бы одну серию")
                return

        dialog = Gtk.FileDialog(title="Выберите папку для скачивания")
        dialog.select_folder(self.window, None, self._on_folder_chosen, (translation, eps_to_download))

    def _on_folder_chosen(self, dialog, result, user_data):
        translation, eps_to_download = user_data
        try:
            gfile = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if gfile is None:
            return

        from pathlib import Path

        download_dir = Path(gfile.get_path())

        from anime_dlp.gui.gtk.download_page import DownloadPage

        self.window.push_page(
            DownloadPage(
                window=self.window,
                item=self.item,
                translation_id=translation["id"],
                eps_to_download=eps_to_download,
                download_dir=download_dir,
            )
        )
