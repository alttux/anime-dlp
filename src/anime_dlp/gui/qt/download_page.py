import subprocess
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from anime_dlp.gui.formatting import SpeedTracker, humanize_bytes
from anime_dlp.gui.qt.widgets import ActionRow, NavHeaderBar, PreferencesGroup, StatusPage
from anime_dlp.gui.qt.workers import DownloadWorker


def _launch_file(window, path: Path):
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        window.show_toast(f"Не удалось открыть: {path}")


def _show_in_folder(window, path: Path):
    try:
        subprocess.run(["explorer", "/select,", str(path)])
    except OSError as exc:
        window.show_toast(f"Не удалось открыть проводник: {exc}")


class _FileRow:
    def __init__(self, filename: str, filepath: Path, window):
        self.filepath = filepath
        self.window = window
        self.row = ActionRow(title=filename)

        self.status_label = QLabel()
        self.status_label.setObjectName("dimLabel")

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(160)
        self.progress_bar.setRange(0, 100)

        self.box = QWidget()
        self.box_layout = QHBoxLayout(self.box)
        self.box_layout.setContentsMargins(0, 0, 0, 0)
        self.box_layout.setSpacing(8)
        self.box_layout.addWidget(self.status_label)
        self.box_layout.addWidget(self.progress_bar)
        self.row.add_suffix(self.box)

        self.speed_tracker = SpeedTracker()
        self._last_speed_text = ""

    def set_progress(self, downloaded: int, total: int):
        fraction = downloaded / total if total else 0.0
        self.progress_bar.setValue(int(fraction * 100))
        speed_text = self.speed_tracker.update(downloaded)
        if speed_text:
            self._last_speed_text = speed_text
        self.status_label.setText(
            f"{humanize_bytes(downloaded)} / {humanize_bytes(total)}  {self._last_speed_text}"
        )

    def set_done(self):
        self.box_layout.removeWidget(self.progress_bar)
        self.progress_bar.deleteLater()
        self.status_label.setText("Готово")

        open_button = QPushButton("📂")
        open_button.setToolTip("Открыть")
        open_button.clicked.connect(lambda: _launch_file(self.window, self.filepath))
        self.box_layout.addWidget(open_button)

        show_button = QPushButton("📁")
        show_button.setToolTip("Показать в папке")
        show_button.clicked.connect(lambda: _show_in_folder(self.window, self.filepath))
        self.box_layout.addWidget(show_button)

        self.row.add_suffix(QLabel("✓"))

    def set_error(self, message: str):
        self.status_label.setText(f"Ошибка: {message}")


class DownloadPage(QWidget):
    def __init__(
        self,
        window,
        item: dict,
        translation_id: str,
        eps_to_download: list[int],
        download_dir: Path,
    ):
        super().__init__()
        self.window = window
        self.item = item
        self.translation_id = translation_id
        self.eps_to_download = eps_to_download
        self.download_dir = download_dir
        self._rows: dict[str, _FileRow] = {}
        self._downloaded_paths: list[Path] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header_bar = NavHeaderBar("Скачивание", show_back=True)
        header_bar.back_clicked.connect(self.window.pop_page)
        outer.addWidget(header_bar)

        self.stack = QStackedWidget()

        content_box = QVBoxLayout()
        content_box.setSpacing(12)
        content_box.setContentsMargins(18, 18, 18, 18)
        content_widget = QWidget()
        content_widget.setLayout(content_box)

        self.summary_label = QLabel(f"Скачивание 0 из {len(eps_to_download)}")
        content_box.addWidget(self.summary_label)

        self.files_group = PreferencesGroup()
        content_box.addWidget(self.files_group)
        content_box.addStretch(1)

        progress_scroll = QScrollArea()
        progress_scroll.setWidgetResizable(True)
        progress_scroll.setWidget(content_widget)
        self.stack.addWidget(progress_scroll)

        self.done_status_page = StatusPage(icon_text="✓", title="Готово!")
        done_scroll = QScrollArea()
        done_scroll.setWidgetResizable(True)
        done_scroll.setWidget(self.done_status_page)
        self.stack.addWidget(done_scroll)

        self.stack.setCurrentIndex(0)
        outer.addWidget(self.stack, 1)

        self._worker = DownloadWorker(item, translation_id, eps_to_download, download_dir, parent=self)
        self._worker.file_started.connect(self._on_file_start)
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.file_error.connect(self._on_file_error)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.fatal_error.connect(lambda msg: self.window.show_toast(f"Ошибка: {msg}"))
        self._worker.start()

    def _on_file_start(self, filename: str, filepath: str, index: int, total: int):
        self.summary_label.setText(f"Скачивание {index} из {total}: {filename}")
        file_row = _FileRow(filename, Path(filepath), self.window)
        self._rows[filename] = file_row
        self.files_group.add(file_row.row)

    def _on_file_progress(self, filename: str, downloaded: int, total: int):
        row = self._rows.get(filename)
        if row:
            row.set_progress(downloaded, total)

    def _on_file_done(self, filename: str, filepath: str):
        row = self._rows.get(filename)
        if row:
            row.set_done()
        self._downloaded_paths.append(Path(filepath))

    def _on_file_error(self, filename: str, message: str):
        row = self._rows.get(filename)
        if row:
            row.set_error(message)
        self.window.show_toast(f"Ошибка скачивания {filename}: {message}")

    def _on_all_done(self):
        self.summary_label.setText(f"Готово! Файлы сохранены в {self.download_dir}")
        self.done_status_page.set_description(str(self.download_dir))

        button_box = QWidget()
        button_layout = QHBoxLayout(button_box)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)
        button_layout.addStretch(1)

        if len(self._downloaded_paths) == 1:
            filepath = self._downloaded_paths[0]

            open_button = QPushButton("Открыть")
            open_button.setObjectName("accentButton")
            open_button.clicked.connect(lambda: _launch_file(self.window, filepath))
            button_layout.addWidget(open_button)

            show_button = QPushButton("Показать в папке")
            show_button.clicked.connect(lambda: _show_in_folder(self.window, filepath))
            button_layout.addWidget(show_button)
        elif self._downloaded_paths:
            open_folder_button = QPushButton("Открыть папку")
            open_folder_button.setObjectName("accentButton")
            open_folder_button.clicked.connect(
                lambda: _launch_file(self.window, self.download_dir)
            )
            button_layout.addWidget(open_folder_button)

        button_layout.addStretch(1)

        self.done_status_page.set_child(button_box)
        self.stack.setCurrentIndex(1)
