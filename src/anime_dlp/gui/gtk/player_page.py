"""Онлайн-плеер (только GTK): HLS-плейлист Kodik через GStreamer.

Конвейер: playbin → gtk4paintablesink → Gtk.Picture. Классический playbin, а
не playbin3: на потоках Kodik у playbin3 (hlsdemux2) перемотка занимала
~6 с, а перемотка назад зависала, у playbin — доли секунды.

Как гарантируется, что играет именно выбранная серия:
  * каждая загрузка (смена серии, качества, повтор после ошибки) получает
    новый self._token; ответы фоновых запросов ссылки с чужим токеном
    отбрасываются — быстрые «следующая, следующая» не перепутают серии;
  * ссылки кэшируются строго по номеру серии (core/playback.py);
  * при остановке конвейера очередь сообщений шины сбрасывается, чтобы
    EOS/ошибка/async-done прошлой серии не применились к новой.

Фазы загрузки: resolving (ждём ссылку) → prerolling (playbin в PAUSED,
буферизует начало) → seeking (переход к сохранённой позиции, если есть) →
ready. В PLAYING переводим только в ready, поэтому при продолжении
просмотра не мелькают первые кадры серии.
"""

import os
import threading

import gi

gi.require_version("Gst", "1.0")

from gi.repository import Adw, Gdk, GLib, Gst, Gtk, Pango  # noqa: E402

from anime_dlp.core import watch_history  # noqa: E402
from anime_dlp.core.playback import DEFAULT_QUALITY, EpisodeSource, PlaybackSource, episode_range  # noqa: E402
from anime_dlp.gui.formatting import format_time  # noqa: E402

_SEEK_STEP = 10
_VOLUME_STEP = 0.05
_HIDE_CONTROLS_MS = 3000
_SCRUB_DEBOUNCE_MS = 200
_TICK_MS = 250
_SAVE_EVERY_S = 5
_DOUBLE_CLICK_MS = 250

# Настройки, общие для всех плееров в пределах запуска программы.
_prefs = {"volume": 1.0, "muted": False, "quality": DEFAULT_QUALITY}
_active_players: set["PlayerPage"] = set()


def player_unavailable_reason() -> str | None:
    """None, если плеер можно открыть; иначе текст для тоста."""
    if not Gst.is_initialized():
        Gst.init(None)
    missing = [
        name
        for name in ("playbin", "gtk4paintablesink", "hlsdemux")
        if Gst.ElementFactory.find(name) is None
    ]
    if missing:
        return (
            "Для просмотра не хватает модулей GStreamer: "
            + ", ".join(missing)
            + ". Установите gst-plugins-good/bad и gst-plugin-gtk4."
        )
    return None


def stop_all() -> None:
    """Останавливает все плееры при выходе (сохраняет позиции просмотра)."""
    for player in list(_active_players):
        player.shutdown()


def _make_video_sink() -> tuple[Gst.Element, Gdk.Paintable]:
    gtk_sink = Gst.ElementFactory.make("gtk4paintablesink", None)
    paintable = gtk_sink.get_property("paintable")
    # С GL-контекстом кадры не копируются через CPU; glsinkbin нужен, чтобы
    # декодер мог отдавать GL-память. ANIME_DLP_PLAYER_GL=0 — аварийный
    # выключатель на случай проблемных драйверов.
    use_gl = os.environ.get("ANIME_DLP_PLAYER_GL", "1") != "0"
    if use_gl and paintable.get_property("gl-context") is not None:
        sink = Gst.ElementFactory.make("glsinkbin", None)
        if sink is not None:
            sink.set_property("sink", gtk_sink)
            return sink, paintable
    return gtk_sink, paintable


class PlayerPage(Adw.NavigationPage):
    def __init__(self, window, item: dict, translation: dict, series_count: int | None, episode: int):
        super().__init__(title=item.get("title", "Плеер"), tag="player")
        self.window = window
        self.item = item
        self.translation = translation
        self.series_count = series_count
        self.shikimori_id = item["shikimori_id"]
        self.source = PlaybackSource(
            self.shikimori_id, translation["id"], episode_range(series_count, translation)
        )

        self._episode = episode
        self._src: EpisodeSource | None = None
        self._quality = _prefs["quality"]
        self._token = 0
        self._phase = "idle"
        self._want_playing = True
        self._buffering = False
        self._pending_seek: float | None = None
        self._duration = 0.0
        self._position = 0.0
        self._last_saved_at = 0.0
        self._scrub_value: float | None = None
        self._scrub_timeout = 0
        self._hide_timeout = 0
        self._single_click_timeout = 0
        self._pointer_in_controls = False
        self._last_motion: tuple[float, float] | None = None
        self._syncing_quality = False
        self._closed = False

        self._build_ui()
        self._build_pipeline()

        self._tick_id = GLib.timeout_add(_TICK_MS, self._on_tick)
        self._popped_handler = window.nav_view.connect("popped", self._on_popped)
        self._fullscreen_handler = window.connect("notify::fullscreened", self._on_fullscreen_changed)
        _active_players.add(self)

        self._load(episode)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self.window_title = Adw.WindowTitle(title=self.item.get("title", ""))
        header = Adw.HeaderBar(title_widget=self.window_title)
        self.toolbar_view = Adw.ToolbarView()
        self.toolbar_view.add_top_bar(header)

        self.picture = Gtk.Picture(
            content_fit=Gtk.ContentFit.CONTAIN,
            hexpand=True,
            vexpand=True,
            css_classes=["player-video"],
        )
        self.overlay = Gtk.Overlay(child=self.picture, css_classes=["player-video"])

        # Загрузка / буферизация
        self.loading_label = Gtk.Label(css_classes=["player-osd-text"])
        self.loading_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            can_target=False,
        )
        spinner = Adw.Spinner(width_request=48, height_request=48)
        self.loading_box.append(spinner)
        self.loading_box.append(self.loading_label)
        self.overlay.add_overlay(self.loading_box)

        # Ошибка
        self.error_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=60)
        retry_button = Gtk.Button(label="Повторить", css_classes=["pill", "suggested-action"], halign=Gtk.Align.CENTER)
        retry_button.connect("clicked", lambda *_: self._retry())
        self.error_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            css_classes=["osd", "player-panel"],
            visible=False,
        )
        self.error_box.append(Gtk.Image(icon_name="dialog-error-symbolic", pixel_size=48))
        self.error_box.append(self.error_label)
        self.error_box.append(retry_button)
        self.overlay.add_overlay(self.error_box)

        # «Пропустить заставку» (таймкоды опенинга/эндинга отдаёт Kodik)
        self.skip_button = Gtk.Button(
            label="Пропустить заставку",
            css_classes=["osd", "pill"],
            halign=Gtk.Align.END,
            valign=Gtk.Align.END,
            margin_end=24,
            margin_bottom=110,
            visible=False,
        )
        self.skip_button.connect("clicked", self._on_skip_clicked)
        self.overlay.add_overlay(self.skip_button)

        self.controls_revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.CROSSFADE,
            reveal_child=True,
            valign=Gtk.Align.END,
        )
        self.controls_revealer.set_child(self._build_controls())
        self.overlay.add_overlay(self.controls_revealer)

        click = Gtk.GestureClick()
        click.connect("pressed", self._on_video_pressed)
        self.picture.add_controller(click)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        self.overlay.add_controller(motion)

        # На окно, а не на страницу: страница получает клавиши, только если
        # фокус внутри неё, а после перехода он может остаться где угодно.
        # CAPTURE — чтобы пробел ставил паузу, а не нажимал кнопку в фокусе.
        self._keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        self._keys.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(self._keys)

        self.toolbar_view.set_content(self.overlay)
        self.set_child(self.toolbar_view)

    def _icon_button(self, icon: str, tooltip: str, callback) -> Gtk.Button:
        button = Gtk.Button(icon_name=icon, tooltip_text=tooltip, css_classes=["flat", "circular"])
        button.connect("clicked", lambda *_: callback())
        return button

    def _build_controls(self) -> Gtk.Box:
        self.position_label = Gtk.Label(label="0:00", css_classes=["numeric"])
        self.duration_label = Gtk.Label(label="0:00", css_classes=["numeric"])
        self.scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=Gtk.Adjustment(lower=0, upper=1, step_increment=_SEEK_STEP, page_increment=60),
            draw_value=False,
            hexpand=True,
            sensitive=False,
        )
        self.scale.connect("change-value", self._on_scale_change_value)

        timeline = Gtk.Box(spacing=12)
        timeline.append(self.position_label)
        timeline.append(self.scale)
        timeline.append(self.duration_label)

        self.prev_button = self._icon_button(
            "media-skip-backward-symbolic", "Предыдущая серия (P)", self._go_previous
        )
        back_button = self._icon_button(
            "media-seek-backward-symbolic", f"Назад на {_SEEK_STEP} с (←)", lambda: self._seek_relative(-_SEEK_STEP)
        )
        self.play_button = self._icon_button(
            "media-playback-pause-symbolic", "Пауза (Пробел)", self._toggle_play
        )
        self.play_button.add_css_class("player-play-button")
        forward_button = self._icon_button(
            "media-seek-forward-symbolic", f"Вперёд на {_SEEK_STEP} с (→)", lambda: self._seek_relative(_SEEK_STEP)
        )
        self.next_button = self._icon_button(
            "media-skip-forward-symbolic", "Следующая серия (N)", self._go_next
        )
        self.episode_label = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END, css_classes=["heading"])

        self.mute_button = self._icon_button("audio-volume-high-symbolic", "Звук (M)", self._toggle_mute)
        self.volume_scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=Gtk.Adjustment(lower=0, upper=1, step_increment=_VOLUME_STEP, page_increment=0.1),
            draw_value=False,
            width_request=110,
            tooltip_text="Громкость (↑/↓)",
        )
        self.volume_scale.set_value(_prefs["volume"])
        self.volume_scale.connect("value-changed", self._on_volume_changed)

        self.quality_model = Gtk.StringList()
        self.quality_dropdown = Gtk.DropDown(model=self.quality_model, tooltip_text="Разрешение", sensitive=False)
        self.quality_dropdown.connect("notify::selected", self._on_quality_selected)

        self.fullscreen_button = self._icon_button(
            "view-fullscreen-symbolic", "Полноэкранный режим (F)", self._toggle_fullscreen
        )

        buttons = Gtk.Box(spacing=6)
        for widget in (
            self.prev_button,
            back_button,
            self.play_button,
            forward_button,
            self.next_button,
            self.episode_label,
            self.mute_button,
            self.volume_scale,
            self.quality_dropdown,
            self.fullscreen_button,
        ):
            buttons.append(widget)

        controls = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            css_classes=["osd", "player-controls"],
        )
        controls.append(timeline)
        controls.append(buttons)

        pointer = Gtk.EventControllerMotion()
        pointer.connect("enter", lambda *_: self._set_pointer_in_controls(True))
        pointer.connect("leave", lambda *_: self._set_pointer_in_controls(False))
        controls.add_controller(pointer)
        return controls

    # ------------------------------------------------------------ pipeline

    def _build_pipeline(self):
        self.playbin = Gst.ElementFactory.make("playbin", None)
        sink, paintable = _make_video_sink()
        self.picture.set_paintable(paintable)
        self.playbin.set_property("video-sink", sink)
        self._apply_volume()
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self._bus_handler = self.bus.connect("message", self._on_bus_message)

    def _stop_pipeline(self):
        self.playbin.set_state(Gst.State.NULL)
        # Сообщения прошлой серии, ещё не разобранные главным циклом, —
        # выбрасываем, чтобы они не применились к новой.
        self.bus.set_flushing(True)
        self.bus.set_flushing(False)

    def shutdown(self):
        """Окончательная остановка: страница закрыта или приложение выходит."""
        if self._closed:
            return
        self._save_progress()
        self._closed = True
        self._token += 1
        _active_players.discard(self)
        for source_id in (self._tick_id, self._scrub_timeout, self._hide_timeout, self._single_click_timeout):
            if source_id:
                GLib.source_remove(source_id)
        self._tick_id = self._scrub_timeout = self._hide_timeout = self._single_click_timeout = 0
        self.playbin.set_state(Gst.State.NULL)
        self.bus.disconnect(self._bus_handler)
        self.bus.remove_signal_watch()
        self.window.remove_controller(self._keys)
        self.window.nav_view.disconnect(self._popped_handler)
        self.window.disconnect(self._fullscreen_handler)
        if self.window.is_fullscreen():
            self.window.unfullscreen()
        self.window.set_cursor(None)
        self.source.close()

    def _on_popped(self, _nav_view, page):
        if page is self:
            self.shutdown()

    # ----------------------------------------------------------- загрузка

    def _load(self, episode: int, start_at: float | None = None, autoplay: bool = True):
        """Начинает воспроизведение серии episode. start_at=None — с
        сохранённой позиции (если есть), иначе — с указанной секунды."""
        self._save_progress()
        self._token += 1
        token = self._token
        self._stop_pipeline()

        self._episode = episode
        self._src = None
        self._phase = "resolving"
        self._want_playing = autoplay
        self._buffering = False
        self._pending_seek = start_at
        self._duration = 0.0
        self._position = start_at or 0.0
        self._scrub_value = None

        self._update_episode_labels()
        self.scale.set_sensitive(False)
        self.scale.get_adjustment().configure(0, 0, 1, _SEEK_STEP, 60, 0)
        self.position_label.set_label("0:00")
        self.duration_label.set_label("0:00")
        self.quality_dropdown.set_sensitive(False)
        self.skip_button.set_visible(False)
        self.error_box.set_visible(False)
        self._show_loading(f"{self._episode_title()} — загрузка…")
        self._update_play_button()
        self._show_controls()

        threading.Thread(target=self._resolve_worker, args=(token, episode), daemon=True).start()

    def _resolve_worker(self, token: int, episode: int):
        try:
            src = self.source.resolve(episode)
        except Exception as exc:
            GLib.idle_add(self._on_resolve_failed, token, str(exc) or type(exc).__name__)
            return
        GLib.idle_add(self._on_resolved, token, src)

    def _on_resolved(self, token: int, src: EpisodeSource):
        # Пока ссылка шла, пользователь мог выбрать другую серию/качество.
        if token != self._token or self._closed or src.episode != self._episode:
            return GLib.SOURCE_REMOVE
        self._src = src
        self._quality = src.pick_quality(self._quality)
        self._fill_quality_dropdown()

        if self._pending_seek is None:
            saved = watch_history.get_position(self.shikimori_id, self._episode)
            self._pending_seek = saved or None
        if self._pending_seek is not None and self._pending_seek < 1:
            self._pending_seek = None

        self.playbin.set_property("uri", src.playlist_url(self._quality))
        self._phase = "prerolling"
        self.playbin.set_state(Gst.State.PAUSED)
        # Пока смотрим эту серию, ссылка на следующую уже будет готова.
        self.source.prefetch(self.source.next_episode(self._episode))
        return GLib.SOURCE_REMOVE

    def _on_resolve_failed(self, token: int, message: str):
        if token != self._token or self._closed:
            return GLib.SOURCE_REMOVE
        self._show_error(f"Не удалось получить ссылку на {self._episode_title().lower()}: {message}")
        return GLib.SOURCE_REMOVE

    def _retry(self):
        self.source.invalidate(self._episode)
        self._load(self._episode, start_at=self._position or None)

    # ---------------------------------------------------------------- bus

    def _on_bus_message(self, _bus, message: Gst.Message):
        if self._closed:
            return
        kind = message.type
        if kind == Gst.MessageType.ASYNC_DONE:
            self._on_async_done()
        elif kind == Gst.MessageType.EOS:
            self._on_eos()
        elif kind == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            print(f"[player] GStreamer error: {error.message} ({debug})")
            self._show_error(f"Ошибка воспроизведения: {error.message}")
        elif kind == Gst.MessageType.BUFFERING:
            self._on_buffering(message.parse_buffering())
        elif kind == Gst.MessageType.DURATION_CHANGED:
            self._query_duration()

    def _on_async_done(self):
        if self._phase == "prerolling":
            self._query_duration()
            target = self._pending_seek
            self._pending_seek = None
            # Если серия почти досмотрена — начинаем сначала, а не с титров.
            if target and (not self._duration or target < self._duration - 15):
                self._phase = "seeking"
                self._do_seek(target)
                return
            self._phase = "ready"
            self._apply_wanted_state()
        elif self._phase == "seeking":
            self._phase = "ready"
            self._apply_wanted_state()
        elif self._phase == "ready" and not self._buffering:
            self._hide_loading()

    def _apply_wanted_state(self):
        self.scale.set_sensitive(True)
        self.quality_dropdown.set_sensitive(len(self._src.qualities) > 1 if self._src else False)
        if self._buffering:
            self._show_loading("Буферизация…")
            return
        self._hide_loading()
        self.playbin.set_state(Gst.State.PLAYING if self._want_playing else Gst.State.PAUSED)
        self._update_play_button()
        self._schedule_hide_controls()

    def _on_buffering(self, percent: int):
        was_buffering = self._buffering
        self._buffering = percent < 100
        if self._phase != "ready":
            return
        if self._buffering and not was_buffering:
            self.playbin.set_state(Gst.State.PAUSED)
            self._show_loading("Буферизация…")
        elif not self._buffering and was_buffering:
            self._hide_loading()
            if self._want_playing:
                self.playbin.set_state(Gst.State.PLAYING)

    def _on_eos(self):
        if self._phase not in ("ready", "seeking"):
            return
        watch_history.mark_watched(self.shikimori_id, self._episode, self.series_count)
        self._position = 0.0
        next_episode = self.source.next_episode(self._episode)
        if next_episode is not None:
            self.window.show_toast(f"{self._episode_title()} просмотрена, включаю следующую")
            self._load(next_episode, start_at=0)
            return
        self._phase = "ended"
        self._want_playing = False
        self.playbin.set_state(Gst.State.PAUSED)
        self._update_play_button()
        self._show_controls()
        self.window.show_toast("Это была последняя серия")

    def _show_error(self, text: str):
        self._phase = "error"
        self._token += 1
        self.playbin.set_state(Gst.State.NULL)
        self._hide_loading()
        self.error_label.set_label(text)
        self.error_box.set_visible(True)
        self._update_play_button()
        self._show_controls()

    # -------------------------------------------------------- перемотка

    def _query_duration(self):
        ok, duration = self.playbin.query_duration(Gst.Format.TIME)
        if ok and duration > 0:
            seconds = duration / Gst.SECOND
            if abs(seconds - self._duration) > 0.5:
                self._duration = seconds
                self.scale.get_adjustment().configure(
                    self.scale.get_value(), 0, seconds, _SEEK_STEP, 60, 0
                )
                self.duration_label.set_label(format_time(seconds))

    def _do_seek(self, seconds: float):
        if self._duration:
            seconds = min(seconds, max(0.0, self._duration - 1))
        seconds = max(0.0, seconds)
        self._position = seconds
        self.playbin.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
            int(seconds * Gst.SECOND),
        )

    def _seek_to(self, seconds: float):
        if self._phase == "ended":
            self._phase = "ready"
        if self._phase == "prerolling":
            self._pending_seek = seconds
            return
        if self._phase != "ready":
            return
        self._do_seek(seconds)
        self.scale.set_value(self._position)
        self.position_label.set_label(format_time(self._position))
        self._show_controls()

    def _seek_relative(self, delta: float):
        self._seek_to(self._current_position() + delta)

    def _current_position(self) -> float:
        if self._phase in ("ready", "ended"):
            ok, position = self.playbin.query_position(Gst.Format.TIME)
            if ok and position >= 0:
                return position / Gst.SECOND
        return self._position

    def _on_scale_change_value(self, _scale, _scroll, value):
        # change-value приходит только от пользователя (перетаскивание,
        # клик, колесо). Перематываем не на каждое движение, а когда
        # ползунок остановился — каждая перемотка HLS — это сетевой запрос.
        if self._phase not in ("ready", "ended"):
            return True
        upper = self.scale.get_adjustment().get_upper()
        self._scrub_value = min(max(value, 0), upper)
        self.position_label.set_label(format_time(self._scrub_value))
        if self._scrub_timeout:
            GLib.source_remove(self._scrub_timeout)
        self._scrub_timeout = GLib.timeout_add(_SCRUB_DEBOUNCE_MS, self._commit_scrub)
        self._show_controls()
        return False

    def _commit_scrub(self):
        self._scrub_timeout = 0
        if self._scrub_value is not None:
            target = self._scrub_value
            self._scrub_value = None
            self._seek_to(target)
        return GLib.SOURCE_REMOVE

    def _on_skip_clicked(self, _button):
        position = self._current_position()
        for start, end in self._src.skip_segments if self._src else ():
            if start <= position < end:
                self._seek_to(end)
                return

    def _on_tick(self):
        if self._phase in ("ready", "ended") and self._scrub_value is None:
            if not self._duration:
                self._query_duration()
            position = self._current_position()
            self._position = position
            self.scale.set_value(position)
            self.position_label.set_label(format_time(position))
            in_skip = any(
                start <= position < end - 2 for start, end in (self._src.skip_segments if self._src else ())
            )
            self.skip_button.set_visible(in_skip)
            if self._phase == "ready" and self._want_playing and position - self._last_saved_at >= _SAVE_EVERY_S:
                self._save_progress()
            elif position < self._last_saved_at:
                self._last_saved_at = position  # перемотали назад
        return GLib.SOURCE_CONTINUE

    def _save_progress(self):
        if self._phase not in ("ready", "ended") or not self._duration:
            return
        position = self._current_position()
        self._last_saved_at = position
        watch_history.save_position(
            self.shikimori_id, self._episode, position, self._duration, self.series_count
        )

    # ------------------------------------------------------- управление

    def _toggle_play(self):
        if self._phase == "error":
            self._retry()
            return
        if self._phase == "ended":
            self._phase = "ready"
            self._want_playing = True
            self._do_seek(0)
            self.playbin.set_state(Gst.State.PLAYING)
            self._update_play_button()
            return
        self._want_playing = not self._want_playing
        if self._phase == "ready" and not self._buffering:
            self.playbin.set_state(Gst.State.PLAYING if self._want_playing else Gst.State.PAUSED)
        if not self._want_playing:
            self._save_progress()
        self._update_play_button()
        self._show_controls()

    def _go_previous(self):
        episode = self.source.previous_episode(self._episode)
        if episode is not None:
            self._load(episode)

    def _go_next(self):
        episode = self.source.next_episode(self._episode)
        if episode is not None:
            self._load(episode)

    def _apply_volume(self):
        volume = _prefs["volume"]
        # Кубическая шкала: громкость на слух меняется равномерно по ползунку.
        self.playbin.set_property("volume", volume**3)
        self.playbin.set_property("mute", _prefs["muted"])
        if _prefs["muted"] or volume == 0:
            icon = "audio-volume-muted-symbolic"
        elif volume < 0.34:
            icon = "audio-volume-low-symbolic"
        elif volume < 0.67:
            icon = "audio-volume-medium-symbolic"
        else:
            icon = "audio-volume-high-symbolic"
        self.mute_button.set_icon_name(icon)

    def _on_volume_changed(self, scale):
        _prefs["volume"] = scale.get_value()
        if _prefs["volume"] > 0:
            _prefs["muted"] = False
        self._apply_volume()
        self._show_controls()

    def _toggle_mute(self):
        _prefs["muted"] = not _prefs["muted"]
        self._apply_volume()
        self._show_controls()

    def _change_volume(self, delta: float):
        self.volume_scale.set_value(min(1.0, max(0.0, self.volume_scale.get_value() + delta)))

    def _fill_quality_dropdown(self):
        self._syncing_quality = True
        qualities = self._src.qualities
        self.quality_model.splice(0, self.quality_model.get_n_items(), [f"{q}p" for q in qualities])
        self.quality_dropdown.set_selected(qualities.index(self._quality))
        self._syncing_quality = False

    def _on_quality_selected(self, dropdown, _pspec):
        if self._syncing_quality or self._src is None:
            return
        index = dropdown.get_selected()
        if index == Gtk.INVALID_LIST_POSITION:
            return
        quality = self._src.qualities[index]
        _prefs["quality"] = quality
        if quality == self._quality:
            return
        self._quality = quality
        # Та же серия, тот же момент — другой плейлист.
        self._load(self._episode, start_at=self._current_position(), autoplay=self._want_playing)

    def _toggle_fullscreen(self):
        if self.window.is_fullscreen():
            self.window.unfullscreen()
        else:
            self.window.fullscreen()

    def _on_fullscreen_changed(self, window, _pspec):
        fullscreen = window.is_fullscreen()
        self.toolbar_view.set_reveal_top_bars(not fullscreen)
        self.fullscreen_button.set_icon_name(
            "view-restore-symbolic" if fullscreen else "view-fullscreen-symbolic"
        )
        self.fullscreen_button.set_tooltip_text(
            "Выйти из полноэкранного режима (F, Esc)" if fullscreen else "Полноэкранный режим (F)"
        )
        self._show_controls()

    # -------------------------------------------- мышь, клавиатура, OSD

    def _on_video_pressed(self, gesture, n_press, _x, _y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        if self._single_click_timeout:
            GLib.source_remove(self._single_click_timeout)
            self._single_click_timeout = 0
        if n_press == 2:
            self._toggle_fullscreen()
        elif n_press == 1:
            # Ждём, не будет ли второго клика: двойной — полноэкранный режим,
            # одиночный — пауза.
            self._single_click_timeout = GLib.timeout_add(_DOUBLE_CLICK_MS, self._on_single_click)

    def _on_single_click(self):
        self._single_click_timeout = 0
        self._toggle_play()
        return GLib.SOURCE_REMOVE

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.META_MASK):
            return False
        key = Gdk.keyval_to_lower(keyval)
        if key in (Gdk.KEY_space, Gdk.KEY_k):
            self._toggle_play()
        elif key == Gdk.KEY_Left:
            self._seek_relative(-_SEEK_STEP)
        elif key == Gdk.KEY_Right:
            self._seek_relative(_SEEK_STEP)
        elif key == Gdk.KEY_Up:
            self._change_volume(_VOLUME_STEP)
        elif key == Gdk.KEY_Down:
            self._change_volume(-_VOLUME_STEP)
        elif key == Gdk.KEY_f:
            self._toggle_fullscreen()
        elif key == Gdk.KEY_Escape and self.window.is_fullscreen():
            self.window.unfullscreen()
        elif key == Gdk.KEY_m:
            self._toggle_mute()
        elif key == Gdk.KEY_n:
            self._go_next()
        elif key == Gdk.KEY_p:
            self._go_previous()
        else:
            return False
        return True

    def _on_motion(self, _controller, x, y):
        # macOS шлёт motion и без движения мыши (например, при смене
        # курсора) — реагируем только на настоящее перемещение.
        if self._last_motion is not None and abs(self._last_motion[0] - x) < 1 and abs(self._last_motion[1] - y) < 1:
            return
        self._last_motion = (x, y)
        self._show_controls()

    def _set_pointer_in_controls(self, inside: bool):
        self._pointer_in_controls = inside
        self._show_controls()

    def _show_controls(self):
        self.controls_revealer.set_reveal_child(True)
        self.overlay.set_cursor(None)
        self._schedule_hide_controls()

    def _schedule_hide_controls(self):
        if self._hide_timeout:
            GLib.source_remove(self._hide_timeout)
        self._hide_timeout = GLib.timeout_add(_HIDE_CONTROLS_MS, self._hide_controls)

    def _hide_controls(self):
        self._hide_timeout = 0
        # Прячем только во время воспроизведения и если курсор не на панели.
        if (
            self._phase == "ready"
            and self._want_playing
            and not self._buffering
            and not self._pointer_in_controls
        ):
            self.controls_revealer.set_reveal_child(False)
            self.overlay.set_cursor_from_name("none")
        return GLib.SOURCE_REMOVE

    # --------------------------------------------------------- подписи

    def _episode_title(self) -> str:
        return "Фильм" if self._episode == 0 else f"Серия {self._episode}"

    def _update_episode_labels(self):
        episodes = self.source.episodes
        if self._episode == 0:
            self.episode_label.set_label("Фильм")
        else:
            self.episode_label.set_label(f"Серия {self._episode} из {episodes[-1]}")
        translation_name = self.translation.get("name", "")
        self.window_title.set_subtitle(f"{self._episode_title()} · {translation_name}")
        self.prev_button.set_sensitive(self.source.previous_episode(self._episode) is not None)
        self.next_button.set_sensitive(self.source.next_episode(self._episode) is not None)
        self.prev_button.set_visible(self._episode != 0)
        self.next_button.set_visible(self._episode != 0)

    def _update_play_button(self):
        playing = self._want_playing and self._phase not in ("error", "ended")
        self.play_button.set_icon_name(
            "media-playback-pause-symbolic" if playing else "media-playback-start-symbolic"
        )
        self.play_button.set_tooltip_text("Пауза (Пробел)" if playing else "Воспроизвести (Пробел)")

    def _show_loading(self, text: str):
        self.loading_label.set_label(text)
        self.loading_box.set_visible(True)

    def _hide_loading(self):
        self.loading_box.set_visible(False)
