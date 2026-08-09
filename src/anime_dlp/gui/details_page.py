import threading

import requests
from gi.repository import Adw, Gdk, GLib, Gtk

from anime_dlp.core.anime_info import extract_anime_info, has_any_info
from anime_dlp.core.anime_service import get_anime_info


class DetailsPage(Adw.NavigationPage):
    def __init__(self, window, item: dict):
        super().__init__(title=item.get("title", "Anime"), tag="details")
        self.window = window
        self.item = item
        self.translations = []
        self.series_count = None

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
            content_fit=Gtk.ContentFit.CONTAIN,
            can_shrink=True,
            halign=Gtk.Align.START,
            valign=Gtk.Align.START,
        )
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
            response = requests.get(poster_url, timeout=10)
            response.raise_for_status()
            data = response.content
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
            info = get_anime_info(self.item["shikimori_id"])
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
        title_label = Gtk.Label(
            label=self.item.get("title", "Anime"),
            wrap=True,
            xalign=0,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            css_classes=["title-1"],
        )

        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=18, hexpand=True
        )
        header_box.append(self.poster_picture)
        header_box.append(title_label)
        self.form_box.append(header_box)

        info_group = self._build_info_group()
        translation_group = Adw.PreferencesGroup(title="Озвучка")
        self.translation_combo = Adw.ComboRow(title="Вариант озвучки")
        model = Gtk.StringList()
        for t in self.translations:
            model.append(f"{t['type']} — {t['name']}")
        self.translation_combo.set_model(model)
        translation_group.add(self.translation_combo)

        self.is_movie = self.series_count == 0 or self.series_count is None

        episodes_group = Adw.PreferencesGroup(title="Серии")
        if self.is_movie:
            row = Adw.ActionRow(title="Фильм", subtitle="Определено как фильм")
            episodes_group.add(row)
        else:
            self.all_episodes_check = Gtk.CheckButton(label="Все серии")
            self.range_episode_check = Gtk.CheckButton(label="Диапазон серий")
            self.single_episode_check = Gtk.CheckButton(label="Одна серия")
            self.range_episode_check.set_group(self.all_episodes_check)
            self.single_episode_check.set_group(self.all_episodes_check)
            self.single_episode_check.set_active(True)

            self.episode_spin = Adw.SpinRow.new_with_range(1, self.series_count, 1)
            self.episode_spin.set_title("Номер серии")

            self.range_from_spin = Adw.SpinRow.new_with_range(1, self.series_count, 1)
            self.range_from_spin.set_title("Серия от")
            self.range_to_spin = Adw.SpinRow.new_with_range(1, self.series_count, 1)
            self.range_to_spin.set_title("Серия до")
            self.range_to_spin.set_value(self.series_count)

            for check in (
                self.single_episode_check,
                self.range_episode_check,
                self.all_episodes_check,
            ):
                check.connect("toggled", self._on_episode_mode_toggled)

            single_row = Adw.ActionRow(title="Одна серия")
            single_row.add_prefix(self.single_episode_check)
            single_row.set_activatable_widget(self.single_episode_check)
            episodes_group.add(single_row)
            episodes_group.add(self.episode_spin)

            range_row = Adw.ActionRow(title="Диапазон серий")
            range_row.add_prefix(self.range_episode_check)
            range_row.set_activatable_widget(self.range_episode_check)
            episodes_group.add(range_row)
            episodes_group.add(self.range_from_spin)
            episodes_group.add(self.range_to_spin)

            all_row = Adw.ActionRow(title="Все серии")
            all_row.add_prefix(self.all_episodes_check)
            all_row.set_activatable_widget(self.all_episodes_check)
            episodes_group.add(all_row)

            self._on_episode_mode_toggled(None)

        sections_flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=False,
            column_spacing=18,
            row_spacing=18,
            max_children_per_line=3,
            min_children_per_line=1,
            hexpand=True,
            halign=Gtk.Align.FILL,
        )

        if info_group is not None:
            sections_flow.append(self._wrap_section(info_group))

        sections_flow.append(self._wrap_section(translation_group))
        sections_flow.append(self._wrap_section(episodes_group))

        self.form_box.append(sections_flow)

    @staticmethod
    def _wrap_section(widget) -> Adw.Clamp:
        clamp = Adw.Clamp(maximum_size=400, tightening_threshold=280)
        clamp.set_child(widget)
        clamp.set_hexpand(True)
        clamp.set_size_request(280, -1)
        return clamp

    def _build_info_group(self) -> Adw.PreferencesGroup | None:
        info = extract_anime_info(self.item)
        if not has_any_info(info):
            return None

        group = Adw.PreferencesGroup(title="Об аниме")

        if info.status:
            row = Adw.ActionRow(title="Статус")
            row.add_suffix(Gtk.Label(label=info.status, css_classes=["heading"], wrap=True, xalign=1))
            group.add(row)

        if info.episodes_total:
            if info.episodes_aired and info.episodes_aired != info.episodes_total:
                episodes = f"{info.episodes_aired}/{info.episodes_total}"
            else:
                episodes = str(info.episodes_total)
            row = Adw.ActionRow(title="Эпизоды")
            row.add_suffix(Gtk.Label(label=episodes, css_classes=["heading"], wrap=True, xalign=1))
            group.add(row)
        elif info.episodes_aired:
            row = Adw.ActionRow(title="Эпизоды")
            row.add_suffix(Gtk.Label(label=str(info.episodes_aired), css_classes=["heading"], wrap=True, xalign=1))
            group.add(row)

        if info.score:
            rating = str(info.score)
            if info.votes:
                rating += f" ({info.votes} голосов)"
            row = Adw.ActionRow(title="Рейтинг")
            row.add_suffix(Gtk.Label(label=rating, css_classes=["heading"], wrap=True, xalign=1))
            group.add(row)

        if info.genres:
            row = Adw.ActionRow(title="Жанры")
            row.add_suffix(Gtk.Label(label=", ".join(info.genres), css_classes=["heading"], wrap=True, xalign=1))
            group.add(row)

        if info.studios:
            row = Adw.ActionRow(title="Студия")
            row.add_suffix(Gtk.Label(label=", ".join(info.studios), css_classes=["heading"], wrap=True, xalign=1))
            group.add(row)

        if info.description:
            expander = Adw.ExpanderRow(title="Описание")
            expander.set_expanded(False)
            label = Gtk.Label(
                label=info.description,
                wrap=True,
                xalign=0,
                margin_top=6,
                margin_bottom=6,
                margin_start=12,
                margin_end=12,
            )
            expander.add_row(label)
            group.add(expander)

        return group

    def _on_episode_mode_toggled(self, button):
        if hasattr(self, "episode_spin"):
            self.episode_spin.set_sensitive(self.single_episode_check.get_active())
        if hasattr(self, "range_from_spin"):
            is_range = self.range_episode_check.get_active()
            self.range_from_spin.set_sensitive(is_range)
            self.range_to_spin.set_sensitive(is_range)

    def _on_download_clicked(self, button):
        selected = self.translation_combo.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION or not self.translations:
            self.window.show_toast("Выберите озвучку")
            return
        translation = self.translations[selected]

        if self.is_movie:
            eps_to_download = [0]
        elif self.all_episodes_check.get_active():
            eps_to_download = list(range(1, self.series_count + 1))
        elif self.range_episode_check.get_active():
            start = int(self.range_from_spin.get_value())
            end = int(self.range_to_spin.get_value())
            if start > end:
                self.window.show_toast("«Серия от» не может быть больше «Серия до»")
                return
            eps_to_download = list(range(start, end + 1))
        else:
            eps_to_download = [int(self.episode_spin.get_value())]

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

        from anime_dlp.gui.download_page import DownloadPage

        self.window.push_page(
            DownloadPage(
                window=self.window,
                item=self.item,
                translation_id=translation["id"],
                eps_to_download=eps_to_download,
                download_dir=download_dir,
            )
        )
