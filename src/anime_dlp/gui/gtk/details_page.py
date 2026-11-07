import re
import threading
from pathlib import Path

import requests
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from anime_dlp.core import favorites, translations as translations_storage, watch_history
from anime_dlp.core.anime_info import AnimeInfo, build_detail_rows, extract_anime_info
from anime_dlp.core.cache import fetch_image_cached
from anime_dlp.gui import prefetch
from anime_dlp.gui.formatting import format_time
from anime_dlp.gui.gtk.related_card import RelatedAnimeCard


class DetailsPage(Adw.NavigationPage):
    def __init__(self, window, item: dict):
        super().__init__(title=item.get("title", "Anime"), tag="details")
        self.window = window
        self.item = item
        self.translations = []
        self.series_count = None
        self.is_movie = False
        self.episode_checks: dict[int, Gtk.CheckButton] = {}
        # Строки и кнопки ▶ по номеру серии (0 — фильм).
        self.episode_rows: dict[int, Adw.ActionRow] = {}
        self.play_buttons: dict[int, Gtk.Button] = {}
        self._syncing_select_all = False
        self._syncing_favorite = False
        self._related_items: list[dict] | None = None
        self.related_box: Gtk.Box | None = None

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
        self.play_main_button = Gtk.Button(
            label="Воспроизвести",
            icon_name="media-playback-start-symbolic",
            css_classes=["pill"],
            sensitive=False,
        )
        self.play_main_button.connect("clicked", self._on_play_main_clicked)

        self.download_button = Gtk.Button(
            label="Скачать",
            css_classes=["suggested-action", "pill"],
            sensitive=False,
        )
        self.download_button.connect("clicked", self._on_download_clicked)

        # pack_end добавляет справа налево: [Воспроизвести] [Скачать]
        self.action_bar.pack_end(self.download_button)
        self.action_bar.pack_end(self.play_main_button)
        content_box.append(self.action_bar)

        toolbar_view.set_content(content_box)
        self.set_child(toolbar_view)

        # Возврат из плеера — обновить отметки «просмотрено» и позиции.
        self.connect("showing", lambda *_: self._refresh_watched())

        threading.Thread(target=self._fetch_info_worker, daemon=True).start()

        if self.item.get("shikimori_id"):
            threading.Thread(target=self._fetch_related_worker, daemon=True).start()

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
            sid = self.item.get("shikimori_id")
            if sid and not self.item.get("material_data", {}).get("description"):
                from anime_dlp.core.anime_service import get_anime_by_shikimori_id

                full_item = get_anime_by_shikimori_id(sid)
                if full_item:
                    for k, v in full_item.items():
                        if k not in self.item or not self.item[k]:
                            self.item[k] = v
                    if "material_data" in full_item:
                        md = self.item.setdefault("material_data", {})
                        for mk, mv in full_item["material_data"].items():
                            if mk not in md or not md[mk]:
                                md[mk] = mv

            info = prefetch.get_or_fetch(self.item["shikimori_id"])
            error = None
        except Exception as exc:
            info = None
            error = str(exc)
        GLib.idle_add(self._on_info_loaded, info, error)

    def _fetch_related_worker(self):
        sid = self.item.get("shikimori_id")
        shiki_url = self.item.get("material_data", {}).get("shikimori_url")
        from anime_dlp.core.anime_service import get_shikimori_additional_info

        info = get_shikimori_additional_info(sid, shiki_url)
        raw_related = info.get("related", []) if isinstance(info, dict) else []
        related_animes = [
            r for r in raw_related
            if isinstance(r, dict) and "/animes/" in r.get("url", "")
        ]
        GLib.idle_add(self._on_related_loaded, related_animes)

    def _on_related_loaded(self, related_animes: list[dict]):
        self._related_items = related_animes
        if self.related_box is not None:
            self._populate_related_box()
        return GLib.SOURCE_REMOVE

    def _populate_related_box(self):
        if self.related_box is None:
            return

        while child := self.related_box.get_first_child():
            self.related_box.remove(child)

        if not self._related_items:
            self.related_box.set_visible(False)
            return

        header_label = Gtk.Label(
            label="Связанные аниме",
            xalign=0,
            css_classes=["title-4", "heading"],
        )
        self.related_box.append(header_label)

        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.NEVER,
            hexpand=True,
        )
        cards_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        cards_box.set_margin_top(4)
        cards_box.set_margin_bottom(8)

        for rel in self._related_items:
            card = RelatedAnimeCard(rel, on_click=self._on_related_clicked)
            cards_box.append(card)

        scrolled.set_child(cards_box)
        self.related_box.append(scrolled)
        self.related_box.set_visible(True)

    def _on_related_clicked(self, related: dict):
        url = related.get("url", "")
        m = re.search(r"/animes/(?:z)?(\d+)", url)
        if not m:
            self.window.show_toast(f"Не удалось открыть «{related.get('name')}»")
            return
        sid = m.group(1)
        item = {
            "title": related.get("name", "Anime"),
            "shikimori_id": sid,
            "material_data": {
                "title": related.get("name"),
                "anime_title": related.get("name"),
                "poster_url": related.get("picture"),
                "anime_poster_url": related.get("picture"),
                "anime_kind": related.get("type"),
            },
        }
        self.window.push_page(DetailsPage(window=self.window, item=item))

    def _on_info_loaded(self, info: dict | None, error: str | None):
        if error or not info:
            self.window.show_toast(f"Ошибка получения информации: {error}")
            self.window.pop_page()
            return GLib.SOURCE_REMOVE

        self.translations = info["translations"]
        self.series_count = info["series_count"]
        # Число серий могло вырасти (онгоинг) — галочка «всё просмотрено»
        # на обложке должна это учитывать.
        watch_history.set_series_count(self.item["shikimori_id"], self.series_count)
        self._build_form()
        self.download_button.set_sensitive(True)
        self.play_main_button.set_sensitive(True)
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

        # Связанные аниме под описанием
        self.related_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True
        )
        self.related_box.set_visible(False)
        self.form_box.append(self.related_box)
        if self._related_items is not None:
            self._populate_related_box()

        translation_group = Adw.PreferencesGroup(title="Озвучка")
        self.translation_combo = Adw.ComboRow(title="Вариант озвучки")
        model = Gtk.StringList()
        for t in self.translations:
            model.append(f"{t['type']} — {t['name']}")
        self.translation_combo.set_model(model)

        saved_idx = translations_storage.find_matching_translation_index(
            self.translations, self.item.get("shikimori_id")
        )
        if saved_idx is not None and saved_idx < len(self.translations):
            self.translation_combo.set_selected(saved_idx)
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
            row.add_suffix(self._make_play_button(0))
            self.episode_rows[0] = row
            episodes_group.add(row)
        else:
            episodes_group.add(self._build_episode_checklist(info))

        self.form_box.append(episodes_group)

        self._apply_series_range()
        self._refresh_watched()

    def _make_play_button(self, episode: int) -> Gtk.Button:
        button = Gtk.Button(
            icon_name="media-playback-start-symbolic",
            tooltip_text="Смотреть" if episode == 0 else f"Смотреть серию {episode}",
            valign=Gtk.Align.CENTER,
            css_classes=["flat", "circular"],
        )
        button.connect("clicked", lambda *_: self._on_play_clicked(episode))
        self.play_buttons[episode] = button
        return button

    def _refresh_watched(self):
        """Подсвечивает просмотренные серии и пишет, где остановились."""
        self._update_play_main_button()
        if not self.episode_rows:
            return
        sid = self.item["shikimori_id"]
        watched = watch_history.watched_episodes(sid)
        for episode, row in self.episode_rows.items():
            if episode in watched:
                row.add_css_class("watched-episode")
                row.set_subtitle("Просмотрено")
                continue
            row.remove_css_class("watched-episode")
            position = watch_history.get_position(sid, episode)
            if position:
                row.set_subtitle(f"Остановились на {format_time(position)}")
            else:
                row.set_subtitle("Определено как фильм" if episode == 0 else "")

    def _save_current_translation(self):
        if not hasattr(self, "translation_combo") or not self.translations:
            return
        selected = self.translation_combo.get_selected()
        if selected != Gtk.INVALID_LIST_POSITION and selected < len(self.translations):
            translations_storage.save_selected_translation(
                self.item.get("shikimori_id"), self.translations[selected]
            )

    def _get_next_play_episode(self) -> int:
        if self.is_movie:
            return 0
        first = 1
        last = self.series_count or 1
        if hasattr(self, "translation_combo") and self.translations:
            selected = self.translation_combo.get_selected()
            if selected != Gtk.INVALID_LIST_POSITION and selected < len(self.translations):
                first, last = self.translations[selected].get(
                    "series_range", (first, last)
                )

        sid = self.item.get("shikimori_id")
        watched = watch_history.watched_episodes(sid)

        for ep in range(first, last + 1):
            if ep not in watched:
                return ep

        return first

    def _update_play_main_button(self):
        if not hasattr(self, "play_main_button") or not self.translations:
            return
        if self.is_movie:
            self.play_main_button.set_tooltip_text("Воспроизвести фильм")
        else:
            ep = self._get_next_play_episode()
            self.play_main_button.set_tooltip_text(f"Воспроизвести (серия {ep})")

    def _on_play_main_clicked(self, _button):
        self._save_current_translation()
        episode = self._get_next_play_episode()
        self._on_play_clicked(episode)

    def _on_play_clicked(self, episode: int):
        self._save_current_translation()
        selected = self.translation_combo.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION or not self.translations:
            self.window.show_toast("Выберите озвучку")
            return
        try:
            from anime_dlp.gui.gtk.player_page import PlayerPage, player_unavailable_reason
        except (ImportError, ValueError) as exc:
            # ValueError — gi.require_version: нет typelib GStreamer.
            self.window.show_toast(f"Плеер недоступен: не установлен GStreamer ({exc})")
            return
        reason = player_unavailable_reason()
        if reason:
            self.window.show_toast(reason)
            return
        self.window.push_page(
            PlayerPage(
                window=self.window,
                item=self.item,
                translation=self.translations[selected],
                series_count=self.series_count,
                episode=episode,
            )
        )

    def _build_header(self, info: AnimeInfo) -> Gtk.Box:
        title_label = Gtk.Label(
            label=self.item.get("title", "Anime"),
            wrap=True,
            xalign=0,
            hexpand=True,
            css_classes=["title-1"],
        )

        sid = self.item.get("shikimori_id")
        shiki_url = (self.item.get("material_data") or {}).get("shikimori_url")
        if not shiki_url and sid:
            shiki_sid = str(sid).strip()
            shiki_sid = shiki_sid if shiki_sid.startswith("z") else f"z{shiki_sid}"
            shiki_url = f"https://shikimori.one/animes/{shiki_sid}"

        self.favorite_button = Gtk.ToggleButton(
            active=favorites.is_favorite(self.item.get("shikimori_id")),
            valign=Gtk.Align.CENTER,
            css_classes=["flat", "circular"],
        )
        self._sync_favorite_button()
        self.favorite_button.connect("toggled", self._on_favorite_toggled)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, hexpand=True)
        title_row.append(title_label)
        if shiki_url:
            shiki_btn = Gtk.LinkButton(
                uri=shiki_url,
                tooltip_text=f"Открыть на Shikimori ({shiki_url})",
                valign=Gtk.Align.CENTER,
                css_classes=["flat"],
            )
            shiki_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            shiki_box.append(Gtk.Image.new_from_icon_name("web-browser-symbolic"))
            shiki_box.append(Gtk.Label(label="Shikimori"))
            shiki_btn.set_child(shiki_box)
            title_row.append(shiki_btn)
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
            row.add_suffix(self._make_play_button(n))
            self.episode_rows[n] = row
            listbox.append(row)

        scrolled = Gtk.ScrolledWindow(min_content_height=300, hexpand=True, vexpand=False)
        scrolled.set_child(listbox)
        container.append(scrolled)
        return container

    def _on_select_all_toggled(self, button):
        if self._syncing_select_all:
            return
        selectable = [c for c in self.episode_checks.values() if c.get_sensitive()]
        # Не полагаемся на get_active(): в состоянии inconsistent оно может
        # быть любым. Правило то же, что в Qt: из «ничего» и «частично» —
        # выбрать все, из «все» — снять.
        active = not all(c.get_active() for c in selectable)
        self._syncing_select_all = True
        for check in selectable:
            check.set_active(active)
        self._syncing_select_all = False
        # Клик по «частично выбранному» флажку оставлял его в состоянии
        # inconsistent, хотя теперь выбраны все серии (или ни одной).
        self._sync_select_all_state()

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
        self._save_current_translation()
        self._apply_series_range()
        self._update_play_main_button()

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
            # Серии вне диапазона озвучки не существует — смотреть нечего.
            self.play_buttons[n].set_sensitive(in_range)
            if not in_range and check.get_active():
                check.set_active(False)
        self._sync_select_all_state()

    def _on_download_clicked(self, button):
        self._save_current_translation()
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

        from anime_dlp.core import settings as app_settings

        ask = app_settings.get_setting("ask_download_folder", True)
        if not ask:
            from anime_dlp.gui.gtk.download_page import DownloadPage

            self.window.push_page(
                DownloadPage(
                    window=self.window,
                    item=self.item,
                    translation_id=translation["id"],
                    eps_to_download=eps_to_download,
                    download_dir=self.window.download_dir,
                )
            )
            return

        dialog = Gtk.FileDialog(title="Выберите папку для скачивания")
        # Стартуем с папки из настроек / -d
        dialog.set_initial_folder(Gio.File.new_for_path(str(self.window.download_dir)))
        dialog.select_folder(self.window, None, self._on_folder_chosen, (translation, eps_to_download))

    def _on_folder_chosen(self, dialog, result, user_data):
        translation, eps_to_download = user_data
        try:
            gfile = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if gfile is None:
            return

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
