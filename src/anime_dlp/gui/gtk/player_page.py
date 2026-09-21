import threading

import gi

gi.require_version("Gst", "1.0")

from gi.repository import Adw, GLib, Gst, Gtk

from anime_dlp.core.playback import PlaybackSources, get_playback_sources


def _format_time(microseconds: int) -> str:
    seconds = max(0, microseconds // 1_000_000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class PlayerPage(Adw.NavigationPage):
    """Kodik HLS player using a GStreamer pipeline rendered in GTK."""

    def __init__(
        self,
        window,
        item: dict,
        translation: dict,
        episode: int,
        series_range: tuple[int, int],
    ):
        title = item.get("title", "Anime")
        super().__init__(title=title, tag=f"player-{episode}")
        Gst.init(None)

        self.window = window
        self.item = item
        self.translation = translation
        self.episode = episode
        self.series_range = series_range
        self.sources: PlaybackSources | None = None
        self.player: Gst.Element | None = None
        self.video_sink: Gst.Element | None = None
        self.bus: Gst.Bus | None = None
        self._bus_handler_id: int | None = None
        self._load_generation = 0
        self._pending_seek = 0
        self._resume_after_load = True
        self._awaiting_preroll = False
        self._quality_sync = False
        self._fullscreen = False
        self._disposed = False

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_bottom(12)

        self.video = Gtk.Picture(
            hexpand=True,
            vexpand=True,
            can_shrink=True,
            content_fit=Gtk.ContentFit.CONTAIN,
        )
        content.append(self.video)

        self.status = Gtk.Label(label="Получение ссылки Kodik...", xalign=0)
        self.status.add_css_class("dim-label")
        content.append(self.status)

        timeline = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.elapsed_label = Gtk.Label(label="0:00")
        timeline.append(self.elapsed_label)
        self.seek_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.seek_scale.set_draw_value(False)
        self.seek_scale.set_hexpand(True)
        self.seek_scale.set_sensitive(False)
        self.seek_scale.connect("change-value", self._on_seek_changed)
        timeline.append(self.seek_scale)
        self.duration_label = Gtk.Label(label="0:00")
        timeline.append(self.duration_label)
        content.append(timeline)

        controls = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            halign=Gtk.Align.CENTER,
        )
        self.previous_button = self._icon_button(
            "media-skip-backward-symbolic", "Предыдущая серия", self._on_previous
        )
        controls.append(self.previous_button)
        controls.append(
            self._icon_button("media-seek-backward-symbolic", "Назад на 5 секунд", self._on_rewind)
        )
        self.play_button = self._icon_button(
            "media-playback-start-symbolic", "Воспроизвести", self._on_play_pause
        )
        self.play_button.add_css_class("suggested-action")
        self.play_button.set_sensitive(False)
        controls.append(self.play_button)
        controls.append(
            self._icon_button("media-seek-forward-symbolic", "Вперёд на 5 секунд", self._on_forward)
        )
        self.next_button = self._icon_button(
            "media-skip-forward-symbolic", "Следующая серия", self._on_next
        )
        controls.append(self.next_button)

        quality_model = Gtk.StringList()
        self.quality_dropdown = Gtk.DropDown(model=quality_model)
        self.quality_dropdown.set_tooltip_text("Качество видео")
        self.quality_dropdown.set_sensitive(False)
        self.quality_dropdown.connect("notify::selected", self._on_quality_changed)
        controls.append(self.quality_dropdown)

        self.fullscreen_button = self._icon_button(
            "view-fullscreen-symbolic", "Полноэкранный режим", self._on_fullscreen
        )
        controls.append(self.fullscreen_button)
        content.append(controls)

        self.episode_label = Gtk.Label(xalign=0, css_classes=["heading"])
        content.prepend(self.episode_label)

        toolbar_view.set_content(content)
        self.set_child(toolbar_view)
        GLib.timeout_add(250, self._update_position)
        self._load_episode(episode, autoplay=True)

    @staticmethod
    def _icon_button(icon_name: str, tooltip: str, callback) -> Gtk.Button:
        button = Gtk.Button(icon_name=icon_name, css_classes=["circular"])
        button.set_tooltip_text(tooltip)
        button.connect("clicked", callback)
        return button

    def _load_episode(self, episode: int, autoplay: bool):
        self._load_generation += 1
        generation = self._load_generation
        self.episode = episode
        self._resume_after_load = autoplay
        self._pending_seek = 0
        self._stop_player()
        self.play_button.set_sensitive(False)
        self.seek_scale.set_sensitive(False)
        self.status.set_label("Получение ссылки Kodik...")
        self.episode_label.set_label(
            self.item.get("title", "Anime")
            if episode == 0
            else f"{self.item.get('title', 'Anime')} — серия {episode}"
        )
        self._sync_episode_buttons()
        threading.Thread(
            target=self._fetch_sources,
            args=(episode, generation),
            daemon=True,
        ).start()

    def _fetch_sources(self, episode: int, generation: int):
        try:
            sources = get_playback_sources(
                str(self.item["shikimori_id"]),
                episode,
                str(self.translation["id"]),
            )
            error = None
        except Exception as exc:
            sources = None
            error = str(exc)
        GLib.idle_add(self._on_sources_loaded, sources, error, generation)

    def _on_sources_loaded(
        self,
        sources: PlaybackSources | None,
        error: str | None,
        generation: int,
    ):
        if self._disposed or generation != self._load_generation:
            return GLib.SOURCE_REMOVE
        if error or sources is None:
            self.status.set_label(f"Не удалось открыть видео: {error}")
            self.window.show_toast(f"Ошибка плеера: {error}")
            return GLib.SOURCE_REMOVE

        previous_quality = self._selected_quality()
        self.sources = sources
        model = Gtk.StringList()
        for quality in sources.qualities:
            model.append(f"{quality}p")
        self._quality_sync = True
        self.quality_dropdown.set_model(model)
        selected_quality = (
            previous_quality
            if previous_quality in sources.qualities
            else sources.default_quality
        )
        self.quality_dropdown.set_selected(sources.qualities.index(selected_quality))
        self._quality_sync = False
        self.quality_dropdown.set_sensitive(True)
        try:
            self._set_player_source(selected_quality, 0, self._resume_after_load)
        except RuntimeError as exc:
            self.status.set_label(f"Не удалось запустить плеер: {exc}")
            self.window.show_toast(f"Ошибка плеера: {exc}")
            self.quality_dropdown.set_sensitive(False)
        return GLib.SOURCE_REMOVE

    def _set_player_source(self, quality: int, position: int, autoplay: bool):
        if self.sources is None:
            return
        self._pending_seek = position
        self._resume_after_load = autoplay
        self._awaiting_preroll = True
        self._stop_player()
        self.status.set_label(f"Загрузка {quality}p...")
        self.player = Gst.ElementFactory.make("playbin3", None)
        if self.player is None:
            self.player = Gst.ElementFactory.make("playbin", None)
        self.video_sink = Gst.ElementFactory.make("gtk4paintablesink", None)
        if self.player is None or self.video_sink is None:
            self._stop_player()
            raise RuntimeError(
                "Не найдены компоненты GStreamer для HLS/GTK4. "
                "Установите hlsdemux и gtk4paintablesink."
            )

        self.player.set_property("uri", self.sources.hls_url(quality))
        self.player.set_property("video-sink", self.video_sink)
        self.video.set_paintable(self.video_sink.get_property("paintable"))
        self.bus = self.player.get_bus()
        self.bus.add_signal_watch()
        self._bus_handler_id = self.bus.connect("message", self._on_bus_message)
        self.player.set_state(Gst.State.PAUSED)

    def _on_bus_message(self, _bus: Gst.Bus, message: Gst.Message):
        if self._disposed or self.player is None:
            return
        message_type = message.type
        if message_type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            detail = error.message
            if debug:
                detail = f"{detail} ({debug})"
            self.status.set_label(f"Ошибка воспроизведения: {detail}")
            self.window.show_toast(f"Ошибка плеера: {error.message}")
            self.play_button.set_sensitive(False)
        elif message_type == Gst.MessageType.EOS:
            if self.episode < self.series_range[1]:
                self._load_episode(self.episode + 1, autoplay=True)
        elif message_type == Gst.MessageType.ASYNC_DONE:
            if self._awaiting_preroll:
                self._awaiting_preroll = False
                self._on_player_prepared()
        elif message_type == Gst.MessageType.BUFFERING:
            percent = message.parse_buffering()
            self.status.set_label(f"Буферизация: {percent}%")
            if percent < 100:
                self.player.set_state(Gst.State.PAUSED)
            elif self._resume_after_load:
                self.player.set_state(Gst.State.PLAYING)

    def _on_player_prepared(self):
        if self.player is None:
            return
        duration = self._query_duration()
        self.seek_scale.set_range(0, max(1, duration // Gst.SECOND))
        self.seek_scale.set_sensitive(duration > 0 and self._is_seekable())
        self.duration_label.set_label(_format_time(duration))
        self.play_button.set_sensitive(True)
        self.status.set_label("")
        if self._pending_seek:
            self._seek_to(min(self._pending_seek, duration))
        if self._resume_after_load:
            self.player.set_state(Gst.State.PLAYING)

    def _query_duration(self) -> int:
        if self.player is None:
            return 0
        success, duration = self.player.query_duration(Gst.Format.TIME)
        return max(0, duration) if success else 0

    def _is_seekable(self) -> bool:
        if self.player is None:
            return False
        success, seekable, _start, _end = self.player.query_seeking(Gst.Format.TIME)
        return success and seekable

    def _is_playing(self) -> bool:
        if self.player is None:
            return False
        _result, current, _pending = self.player.get_state(0)
        return current == Gst.State.PLAYING

    def _seek_to(self, position: int):
        if self.player is not None and self._is_seekable():
            self.player.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                max(0, position),
            )

    def _update_position(self):
        if self._disposed:
            return GLib.SOURCE_REMOVE
        if self.player is not None:
            success, timestamp = self.player.query_position(Gst.Format.TIME)
            if not success:
                return GLib.SOURCE_CONTINUE
            timestamp = max(0, timestamp)
            self.elapsed_label.set_label(_format_time(timestamp))
            self.seek_scale.set_value(timestamp // Gst.SECOND)
            playing = self._is_playing()
            self.play_button.set_icon_name(
                "media-playback-pause-symbolic" if playing else "media-playback-start-symbolic"
            )
            self.play_button.set_tooltip_text("Пауза" if playing else "Воспроизвести")
        return GLib.SOURCE_CONTINUE

    def _on_seek_changed(self, _scale, _scroll_type, value: float):
        self._seek_to(int(value * Gst.SECOND))
        return False

    def _seek_relative(self, seconds: int):
        if self.player is None or not self._is_seekable():
            return
        success, timestamp = self.player.query_position(Gst.Format.TIME)
        if not success:
            return
        target = timestamp + seconds * Gst.SECOND
        self._seek_to(min(max(0, target), self._query_duration()))

    def _on_rewind(self, _button):
        self._seek_relative(-5)

    def _on_forward(self, _button):
        self._seek_relative(5)

    def _on_play_pause(self, _button):
        if self.player is None:
            return
        if self._is_playing():
            self._resume_after_load = False
            self.player.set_state(Gst.State.PAUSED)
        else:
            self._resume_after_load = True
            self.player.set_state(Gst.State.PLAYING)

    def _selected_quality(self) -> int | None:
        if self.sources is None:
            return None
        selected = self.quality_dropdown.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION or selected >= len(self.sources.qualities):
            return None
        return self.sources.qualities[selected]

    def _on_quality_changed(self, _dropdown, _pspec):
        if self._quality_sync or self.player is None:
            return
        quality = self._selected_quality()
        if quality is None:
            return
        success, position = self.player.query_position(Gst.Format.TIME)
        self._set_player_source(
            quality,
            position if success else 0,
            self._is_playing(),
        )

    def _sync_episode_buttons(self):
        first, last = self.series_range
        self.previous_button.set_sensitive(self.episode > first)
        self.next_button.set_sensitive(self.episode < last)

    def _on_previous(self, _button):
        if self.episode > self.series_range[0]:
            self._load_episode(self.episode - 1, autoplay=True)

    def _on_next(self, _button):
        if self.episode < self.series_range[1]:
            self._load_episode(self.episode + 1, autoplay=True)

    def _on_fullscreen(self, _button):
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.window.fullscreen()
            self.fullscreen_button.set_icon_name("view-restore-symbolic")
            self.fullscreen_button.set_tooltip_text("Выйти из полноэкранного режима")
        else:
            self.window.unfullscreen()
            self.fullscreen_button.set_icon_name("view-fullscreen-symbolic")
            self.fullscreen_button.set_tooltip_text("Полноэкранный режим")

    def _stop_player(self):
        if self.bus is not None:
            if self._bus_handler_id is not None:
                self.bus.disconnect(self._bus_handler_id)
            self.bus.remove_signal_watch()
        if self.player is not None:
            self.player.set_state(Gst.State.NULL)
        self.video.set_paintable(None)
        self.player = None
        self.video_sink = None
        self.bus = None
        self._bus_handler_id = None
        self._awaiting_preroll = False

    def cleanup(self):
        self._disposed = True
        self._load_generation += 1
        self._stop_player()
        if self._fullscreen:
            self.window.unfullscreen()
            self._fullscreen = False
