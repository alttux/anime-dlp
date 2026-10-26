import threading
from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk

from anime_dlp.core.episodes import BatchResult, DownloadEvents, EpisodeJob, download_episodes
from anime_dlp.gui.desktop import reveal_in_file_manager
from anime_dlp.gui.formatting import SpeedTracker, humanize_bytes, summarize_result


def _launch_file(window, path: Path):
    launcher = Gtk.FileLauncher(file=Gio.File.new_for_path(str(path)))

    def on_finished(launcher, result):
        try:
            launcher.launch_finish(result)
        except GLib.Error as exc:
            window.show_toast(f"Не удалось открыть: {exc.message}")

    launcher.launch(window, None, on_finished)


def _show_in_folder(window, path: Path):
    # Windows (MSYS2) и macOS: штатная команда ОС «выделить файл в папке».
    if reveal_in_file_manager(path):
        return
    # Gtk.FileLauncher.open_containing_folder() goes through the
    # xdg-desktop-portal OpenDirectory call, which on some desktops/portal
    # backends silently activates the file manager without ever showing a
    # window. Calling org.freedesktop.FileManager1.ShowItems directly is
    # what actually works across GNOME/KDE/Xfce file managers.
    uri = Gio.File.new_for_path(str(path)).get_uri()

    def call_done(proxy, result, _data=None):
        try:
            proxy.call_finish(result)
        except GLib.Error:
            _launch_file(window, path.parent)

    def proxy_ready(_source, result, _data=None):
        try:
            proxy = Gio.DBusProxy.new_for_bus_finish(result)
        except GLib.Error:
            _launch_file(window, path.parent)
            return
        proxy.call(
            "ShowItems",
            GLib.Variant("(ass)", ([uri], "")),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
            call_done,
        )

    Gio.DBusProxy.new_for_bus(
        Gio.BusType.SESSION,
        Gio.DBusProxyFlags.NONE,
        None,
        "org.freedesktop.FileManager1",
        "/org/freedesktop/FileManager1",
        "org.freedesktop.FileManager1",
        None,
        proxy_ready,
    )


class _FileRow:
    def __init__(self, filename: str, filepath: Path, window):
        self.filepath = filepath
        self.window = window
        self.row = Adw.ActionRow(title=filename)
        self.progress_bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER, hexpand=True)
        self.progress_bar.set_size_request(160, -1)
        self.status_label = Gtk.Label(css_classes=["dim-label"])
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.box.append(self.status_label)
        self.box.append(self.progress_bar)
        self.row.add_suffix(self.box)
        self.speed_tracker = SpeedTracker()
        self._last_speed_text = ""

    def set_progress(self, downloaded: int, total: int):
        fraction = downloaded / total if total else 0.0
        self.progress_bar.set_fraction(fraction)
        speed_text = self.speed_tracker.update(downloaded)
        if speed_text:
            self._last_speed_text = speed_text
        self.status_label.set_label(
            f"{humanize_bytes(downloaded)} / {humanize_bytes(total)}  {self._last_speed_text}"
        )

    def set_done(self):
        self.box.remove(self.progress_bar)
        self.status_label.set_label("Готово")

        open_button = Gtk.Button(
            icon_name="document-open-symbolic",
            tooltip_text="Открыть",
            valign=Gtk.Align.CENTER,
        )
        open_button.connect("clicked", self._on_open_clicked)
        self.box.append(open_button)

        show_button = Gtk.Button(
            icon_name="folder-symbolic",
            tooltip_text="Показать в папке",
            valign=Gtk.Align.CENTER,
        )
        show_button.connect("clicked", self._on_show_in_folder_clicked)
        self.box.append(show_button)

        self.row.add_suffix(Gtk.Image.new_from_icon_name("object-select-symbolic"))

    def _on_open_clicked(self, button):
        _launch_file(self.window, self.filepath)

    def _on_show_in_folder_clicked(self, button):
        _show_in_folder(self.window, self.filepath)

    def set_error(self, message: str):
        self.status_label.set_label(f"Ошибка: {message}")
        self.status_label.set_tooltip_text(message)


class _GLibEvents(DownloadEvents):
    """Перекидывает колбэки core.episodes из фонового потока в главный цикл."""

    def __init__(self, page: "DownloadPage"):
        self.page = page

    def on_start(self, job: EpisodeJob, quality: int) -> None:
        GLib.idle_add(self.page._on_file_start, job)

    def on_progress(self, job: EpisodeJob, downloaded: int, total: int) -> None:
        GLib.idle_add(self.page._on_file_progress, job.filename, downloaded, total)

    def on_done(self, job: EpisodeJob) -> None:
        GLib.idle_add(self.page._on_file_done, job)

    def on_error(self, job: EpisodeJob, message: str) -> None:
        GLib.idle_add(self.page._on_file_error, job.filename, message)


class DownloadPage(Adw.NavigationPage):
    def __init__(
        self,
        window,
        item: dict,
        translation_id: str,
        eps_to_download: list[int],
        download_dir: Path,
    ):
        super().__init__(title="Скачивание", tag="download")
        self.window = window
        self.item = item
        self.translation_id = translation_id
        self.eps_to_download = eps_to_download
        self.download_dir = download_dir
        self._rows: dict[str, _FileRow] = {}
        self._downloaded_paths: list[Path] = []
        self._cancel_event = threading.Event()

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.cancel_button = Gtk.Button(label="Отменить", css_classes=["destructive-action"])
        self.cancel_button.connect("clicked", self._on_cancel_clicked)
        header.pack_end(self.cancel_button)
        toolbar_view.add_top_bar(header)

        self.stack = Gtk.Stack()

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(18)
        content_box.set_margin_bottom(18)
        content_box.set_margin_start(18)
        content_box.set_margin_end(18)

        self.summary_label = Gtk.Label(
            label=f"Скачивание 0 из {len(eps_to_download)}", xalign=0
        )
        content_box.append(self.summary_label)

        self.files_group = Adw.PreferencesGroup()
        content_box.append(self.files_group)

        progress_scrolled = Gtk.ScrolledWindow(vexpand=True)
        progress_scrolled.set_child(content_box)
        self.stack.add_named(progress_scrolled, "progress")

        self.done_status_page = Adw.StatusPage(
            icon_name="object-select-symbolic", title="Готово!"
        )
        done_scrolled = Gtk.ScrolledWindow(vexpand=True)
        done_scrolled.set_child(self.done_status_page)
        self.stack.add_named(done_scrolled, "done")

        self.stack.set_visible_child_name("progress")

        toolbar_view.set_content(self.stack)
        self.set_child(toolbar_view)

        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        try:
            result = download_episodes(
                self.item,
                self.translation_id,
                self.eps_to_download,
                self.download_dir,
                _GLibEvents(self),
                self._cancel_event,
            )
        except Exception as exc:
            GLib.idle_add(self.window.show_toast, f"Ошибка: {exc}")
            result = BatchResult(done=[], failed=[], cancelled=False)
        GLib.idle_add(self._on_all_done, result)

    def _on_cancel_clicked(self, _button):
        # Остановка не мгновенная (поток дописывает текущий блок) — экран
        # «Отменено» покажет _on_all_done, когда поток действительно встанет.
        self._cancel_event.set()
        self.cancel_button.set_sensitive(False)
        self.summary_label.set_label("Отмена...")

    def _on_file_start(self, job: EpisodeJob):
        self.summary_label.set_label(f"Скачивание {job.index} из {job.total}: {job.filename}")
        file_row = _FileRow(job.filename, job.filepath, self.window)
        self._rows[job.filename] = file_row
        self.files_group.add(file_row.row)
        return GLib.SOURCE_REMOVE

    def _on_file_progress(self, filename: str, downloaded: int, total: int):
        row = self._rows.get(filename)
        if row:
            row.set_progress(downloaded, total)
        return GLib.SOURCE_REMOVE

    def _on_file_done(self, job: EpisodeJob):
        row = self._rows.get(job.filename)
        if row:
            row.set_done()
        self._downloaded_paths.append(job.filepath)
        return GLib.SOURCE_REMOVE

    def _on_file_error(self, filename: str, message: str):
        row = self._rows.get(filename)
        if row:
            row.set_error(message)
        self.window.show_toast(f"Ошибка скачивания {filename}: {message}")
        return GLib.SOURCE_REMOVE

    def _on_all_done(self, result: BatchResult):
        self.cancel_button.set_visible(False)
        title, description = summarize_result(result, self.download_dir)
        self.summary_label.set_label(f"{title} {description}")
        self.done_status_page.set_title(title)
        self.done_status_page.set_description(description)
        if result.cancelled or result.failed:
            self.done_status_page.set_icon_name("dialog-warning-symbolic")

        button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
        )

        if len(self._downloaded_paths) == 1:
            filepath = self._downloaded_paths[0]

            open_button = Gtk.Button(label="Открыть", css_classes=["suggested-action"])
            open_button.connect("clicked", lambda b: _launch_file(self.window, filepath))
            button_box.append(open_button)

            show_button = Gtk.Button(label="Показать в папке")
            show_button.connect("clicked", lambda b: _show_in_folder(self.window, filepath))
            button_box.append(show_button)
        elif self._downloaded_paths:
            open_folder_button = Gtk.Button(
                label="Открыть папку", css_classes=["suggested-action"]
            )
            open_folder_button.connect(
                "clicked", lambda b: _launch_file(self.window, self.download_dir)
            )
            button_box.append(open_folder_button)

        self.done_status_page.set_child(button_box)
        self.stack.set_visible_child_name("done")
        return GLib.SOURCE_REMOVE
