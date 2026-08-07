import threading
from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk

from anime_dlp.core.anime_service import get_download_link
from anime_dlp.core.downloader import download_episode
from anime_dlp.filenames import sanitize_filename
from anime_dlp.gui.formatting import SpeedTracker, humanize_bytes


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

        self.row.add_suffix(Gtk.Image.new_from_icon_name("emblem-ok-symbolic"))

    def _on_open_clicked(self, button):
        launcher = Gtk.FileLauncher(file=Gio.File.new_for_path(str(self.filepath)))
        launcher.launch(self.window, None, self._on_open_finished)

    def _on_open_finished(self, launcher, result):
        try:
            launcher.launch_finish(result)
        except GLib.Error as exc:
            self.window.show_toast(f"Не удалось открыть: {exc.message}")

    def _on_show_in_folder_clicked(self, button):
        launcher = Gtk.FileLauncher(file=Gio.File.new_for_path(str(self.filepath)))
        launcher.open_containing_folder(self.window, None, self._on_show_finished)

    def _on_show_finished(self, launcher, result):
        try:
            launcher.open_containing_folder_finish(result)
        except GLib.Error as exc:
            self.window.show_toast(f"Не удалось открыть папку: {exc.message}")

    def set_error(self, message: str):
        self.status_label.set_label(f"Ошибка: {message}")


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

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

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

        self.stack.add_named(content_box, "progress")

        self.done_status_page = Adw.StatusPage(
            icon_name="emblem-ok-symbolic", title="Готово!"
        )
        self.stack.add_named(self.done_status_page, "done")

        self.stack.set_visible_child_name("progress")

        toolbar_view.set_content(self.stack)
        self.set_child(toolbar_view)

        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        try:
            sid = self.item["shikimori_id"]
            total = len(self.eps_to_download)
            for index, ep in enumerate(self.eps_to_download, 1):
                safe_title = sanitize_filename(self.item["title"])
                filename = f"{safe_title}.mp4" if ep == 0 else f"{ep}.mp4"
                try:
                    link, quality, _ = get_download_link(sid, ep, self.translation_id)
                    filepath = self.download_dir / filename

                    GLib.idle_add(self._on_file_start, filename, filepath, index, total)

                    def on_progress(downloaded, total_bytes, filename=filename):
                        GLib.idle_add(self._on_file_progress, filename, downloaded, total_bytes)

                    download_episode(link, filepath, quality, on_progress=on_progress)
                    GLib.idle_add(self._on_file_done, filename)
                except Exception as exc:
                    if filename not in self._rows:
                        filepath = self.download_dir / filename
                        GLib.idle_add(self._on_file_start, filename, filepath, index, total)
                    GLib.idle_add(self._on_file_error, filename, str(exc))
            GLib.idle_add(self._on_all_done)
        except Exception as exc:
            GLib.idle_add(self.window.show_toast, f"Ошибка: {exc}")

    def _on_file_start(self, filename: str, filepath: Path, index: int, total: int):
        self.summary_label.set_label(f"Скачивание {index} из {total}: {filename}")
        file_row = _FileRow(filename, filepath, self.window)
        self._rows[filename] = file_row
        self.files_group.add(file_row.row)
        return GLib.SOURCE_REMOVE

    def _on_file_progress(self, filename: str, downloaded: int, total: int):
        row = self._rows.get(filename)
        if row:
            row.set_progress(downloaded, total)
        return GLib.SOURCE_REMOVE

    def _on_file_done(self, filename: str):
        row = self._rows.get(filename)
        if row:
            row.set_done()
        return GLib.SOURCE_REMOVE

    def _on_file_error(self, filename: str, message: str):
        row = self._rows.get(filename)
        if row:
            row.set_error(message)
        self.window.show_toast(f"Ошибка скачивания {filename}: {message}")
        return GLib.SOURCE_REMOVE

    def _on_all_done(self):
        self.summary_label.set_label(f"Готово! Файлы сохранены в {self.download_dir}")
        self.done_status_page.set_description(str(self.download_dir))
        self.stack.set_visible_child_name("done")
        return GLib.SOURCE_REMOVE
