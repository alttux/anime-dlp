import threading

from gi.repository import Adw, GLib, Gtk

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

        self.stack = Gtk.Stack()

        spinner_box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        spinner_box.append(Adw.Spinner())
        self.stack.add_named(spinner_box, "loading")

        self.form_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.form_box.set_margin_top(18)
        self.form_box.set_margin_bottom(18)
        self.form_box.set_margin_start(18)
        self.form_box.set_margin_end(18)

        form_scrolled = Gtk.ScrolledWindow(vexpand=True)
        form_scrolled.set_child(self.form_box)
        self.stack.add_named(form_scrolled, "form")

        self.stack.set_visible_child_name("loading")

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
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
        translation_group = Adw.PreferencesGroup(title="Озвучка")
        self.translation_combo = Adw.ComboRow(title="Вариант озвучки")
        model = Gtk.StringList()
        for t in self.translations:
            model.append(f"{t['type']} — {t['name']}")
        self.translation_combo.set_model(model)
        translation_group.add(self.translation_combo)
        self.form_box.append(translation_group)

        self.is_movie = self.series_count == 0 or self.series_count is None

        episodes_group = Adw.PreferencesGroup(title="Серии")
        if self.is_movie:
            row = Adw.ActionRow(title="Фильм", subtitle="Определено как фильм")
            episodes_group.add(row)
        else:
            self.all_episodes_check = Gtk.CheckButton(label="Все серии")
            self.single_episode_check = Gtk.CheckButton(label="Одна серия")
            self.single_episode_check.set_group(self.all_episodes_check)
            self.single_episode_check.set_active(True)

            self.episode_spin = Adw.SpinRow.new_with_range(1, self.series_count, 1)
            self.episode_spin.set_title("Номер серии")

            self.single_episode_check.connect(
                "toggled", self._on_episode_mode_toggled
            )
            self.all_episodes_check.connect("toggled", self._on_episode_mode_toggled)

            single_row = Adw.ActionRow(title="Одна серия")
            single_row.add_prefix(self.single_episode_check)
            single_row.set_activatable_widget(self.single_episode_check)
            episodes_group.add(single_row)
            episodes_group.add(self.episode_spin)

            all_row = Adw.ActionRow(title="Все серии")
            all_row.add_prefix(self.all_episodes_check)
            all_row.set_activatable_widget(self.all_episodes_check)
            episodes_group.add(all_row)

        self.form_box.append(episodes_group)

    def _on_episode_mode_toggled(self, button):
        if hasattr(self, "episode_spin"):
            self.episode_spin.set_sensitive(self.single_episode_check.get_active())

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
