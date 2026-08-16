from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from anime_dlp.core.anime_info import AnimeInfo, build_detail_rows, extract_anime_info
from anime_dlp.gui.qt.pixmap_utils import round_pixmap
from anime_dlp.gui.qt.widgets import ActionRow, ComboRow, FlowLayout, NavHeaderBar, PreferencesGroup
from anime_dlp.gui.qt.workers import AnimeInfoWorker, PosterWorker

POSTER_WIDTH = 200
POSTER_HEIGHT = 280
POSTER_RADIUS = 12


class _EpisodeRow(QFrame):
    toggled = pyqtSignal(int, bool)

    def __init__(self, number: int, duration: int | None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        self.checkbox = QCheckBox(f"Серия {number}")
        self.checkbox.toggled.connect(lambda checked: self.toggled.emit(number, checked))
        layout.addWidget(self.checkbox, 1)

        if duration:
            duration_label = QLabel(f"~{duration} мин")
            duration_label.setObjectName("dimLabel")
            layout.addWidget(duration_label)

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)

    def set_enabled(self, enabled: bool):
        self.checkbox.setEnabled(enabled)


class DetailsPage(QWidget):
    def __init__(self, window, item: dict):
        super().__init__()
        self.window = window
        self.item = item
        self.translations: list[dict] = []
        self.series_count = None
        self.is_movie = False
        self.episode_rows: dict[int, _EpisodeRow] = {}
        self._syncing_select_all = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header_bar = NavHeaderBar(item.get("title", "Anime"), show_back=True)
        header_bar.back_clicked.connect(self.window.pop_page)
        outer.addWidget(header_bar)

        content_box = QVBoxLayout()
        content_box.setContentsMargins(0, 0, 0, 0)
        content_container = QWidget()
        content_container.setLayout(content_box)

        self.stack = QStackedWidget()

        loading_page = QWidget()
        loading_layout = QVBoxLayout(loading_page)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner = QProgressBar()
        spinner.setRange(0, 0)
        spinner.setFixedWidth(200)
        spinner.setTextVisible(False)
        loading_layout.addWidget(spinner)
        self.stack.addWidget(loading_page)

        self.form_box = QVBoxLayout()
        self.form_box.setSpacing(18)
        self.form_box.setContentsMargins(18, 18, 18, 18)
        form_widget = QWidget()
        form_widget.setLayout(self.form_box)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(form_widget)
        self.stack.addWidget(form_scroll)

        self.stack.setCurrentIndex(0)
        content_box.addWidget(self.stack, 1)

        self.poster_label = QLabel()
        self.poster_label.setFixedSize(POSTER_WIDTH, POSTER_HEIGHT)
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.poster_label.setVisible(False)

        action_bar = QWidget()
        action_bar_layout = QHBoxLayout(action_bar)
        action_bar_layout.setContentsMargins(12, 8, 12, 8)
        action_bar_layout.addStretch(1)
        self.download_button = QPushButton("Скачать")
        self.download_button.setObjectName("accentButton")
        self.download_button.clicked.connect(self._on_download_clicked)
        action_bar_layout.addWidget(self.download_button)
        content_box.addWidget(action_bar)

        outer.addWidget(content_container, 1)

        self._info_worker = AnimeInfoWorker(item["shikimori_id"], parent=self)
        self._info_worker.finished_info.connect(self._on_info_loaded)
        self._info_worker.start()

        self._poster_worker = None
        poster_url = extract_anime_info(self.item).poster_url
        if poster_url:
            self._poster_worker = PosterWorker(poster_url, parent=self)
            self._poster_worker.finished_poster.connect(self._on_poster_loaded)
            self._poster_worker.start()

    def _on_poster_loaded(self, data: bytes, error: str):
        if error or not data:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        pixmap = pixmap.scaled(
            POSTER_WIDTH,
            POSTER_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        pixmap = round_pixmap(pixmap, radius=POSTER_RADIUS)
        self.poster_label.setPixmap(pixmap)
        # Постер может загрузиться раньше информации об аниме — до
        # _build_form() poster_label ещё ни к чему не прикреплён (без
        # родителя), и setVisible(True) на нём превращает его в отдельное
        # плавающее окно верхнего уровня. Показываем только если он уже
        # добавлен в layout; иначе _build_form() сам покажет его при сборке.
        if self.poster_label.parentWidget() is not None:
            self.poster_label.setVisible(True)

    def _on_info_loaded(self, info: dict, error: str):
        if error or not info:
            self.window.show_toast(f"Ошибка получения информации: {error}")
            self.window.pop_page()
            return

        self.translations = info["translations"]
        self.series_count = info["series_count"]
        self._build_form()
        self.stack.setCurrentIndex(1)

    def _build_form(self):
        info = extract_anime_info(self.item)

        self.form_box.addLayout(self._build_header(info))

        if not self.poster_label.pixmap().isNull():
            self.poster_label.setVisible(True)

        key_value_widget = self._build_key_value_grid(info)
        if key_value_widget is not None:
            self.form_box.addWidget(key_value_widget)

        if info.description:
            description_label = QLabel(info.description)
            description_label.setWordWrap(True)
            self.form_box.addWidget(description_label)

        translation_group = PreferencesGroup(title="Озвучка")
        self.translation_combo = ComboRow("Вариант озвучки")
        self.translation_combo.set_items(
            [f"{t['type']} — {t['name']}" for t in self.translations]
        )
        self.translation_combo.combo.currentIndexChanged.connect(self._on_translation_changed)
        translation_group.add(self.translation_combo)
        self.form_box.addWidget(translation_group)

        self.is_movie = self.series_count == 0 or self.series_count is None

        episodes_group = PreferencesGroup(title="Серии")
        if self.is_movie:
            row = ActionRow(title="Фильм", subtitle="Определено как фильм")
            episodes_group.add(row)
        else:
            episodes_group.add(self._build_episode_checklist(info))

        self.form_box.addWidget(episodes_group)

        self._apply_series_range()

    def _build_header(self, info: AnimeInfo) -> QHBoxLayout:
        title_label = QLabel(self.item.get("title", "Anime"))
        title_label.setObjectName("title1")
        title_label.setWordWrap(True)

        text_box = QVBoxLayout()
        text_box.setSpacing(6)
        text_box.addWidget(title_label)

        if info.title_orig:
            subtitle_label = QLabel(info.title_orig)
            subtitle_label.setObjectName("dimLabel")
            subtitle_label.setWordWrap(True)
            text_box.addWidget(subtitle_label)

        pills = self._build_genre_pills(info.genres)
        if pills is not None:
            text_box.addWidget(pills)
        text_box.addStretch(1)

        header_row = QHBoxLayout()
        header_row.setSpacing(18)
        header_row.addWidget(self.poster_label)
        header_row.addLayout(text_box, 1)
        return header_row

    @staticmethod
    def _build_genre_pills(genres: list[str]) -> QWidget | None:
        if not genres:
            return None
        container = QWidget()
        flow_layout = FlowLayout(container, spacing=6)
        for genre in genres:
            label = QLabel(genre)
            label.setObjectName("pillBadge")
            flow_layout.addWidget(label)
        return container

    @staticmethod
    def _build_key_value_grid(info: AnimeInfo) -> QWidget | None:
        rows = build_detail_rows(info)
        if not rows:
            return None

        container = QWidget()
        grid = QGridLayout(container)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)
        for row_index, (label, value) in enumerate(rows):
            label_widget = QLabel(label)
            label_widget.setObjectName("dimLabel")
            grid.addWidget(label_widget, row_index, 0)

            value_widget = QLabel(value)
            value_widget.setWordWrap(True)
            grid.addWidget(value_widget, row_index, 1)
        grid.setColumnStretch(1, 1)
        return container

    def _build_episode_checklist(self, info: AnimeInfo) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.select_all_check = QCheckBox("Выбрать все")
        self.select_all_check.setTristate(True)
        self.select_all_check.stateChanged.connect(self._on_select_all_toggled)
        layout.addWidget(self.select_all_check)

        self.episode_rows = {}
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)
        for n in range(1, self.series_count + 1):
            row = _EpisodeRow(n, info.duration)
            row.toggled.connect(self._on_episode_toggled)
            self.episode_rows[n] = row
            list_layout.addWidget(row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(320)
        scroll.setWidget(list_widget)
        layout.addWidget(scroll)
        return container

    def _on_select_all_toggled(self, state: int):
        if self._syncing_select_all:
            return
        self._syncing_select_all = True
        checked = Qt.CheckState(state) == Qt.CheckState.Checked
        for row in self.episode_rows.values():
            if row.checkbox.isEnabled():
                row.set_checked(checked)
        self._syncing_select_all = False

    def _on_episode_toggled(self, _number: int, _checked: bool):
        if self._syncing_select_all:
            return
        self._sync_select_all_state()

    def _sync_select_all_state(self):
        selectable = [r for r in self.episode_rows.values() if r.checkbox.isEnabled()]
        checked = [r for r in selectable if r.is_checked()]
        self._syncing_select_all = True
        if not selectable or not checked:
            self.select_all_check.setCheckState(Qt.CheckState.Unchecked)
        elif len(checked) == len(selectable):
            self.select_all_check.setCheckState(Qt.CheckState.Checked)
        else:
            self.select_all_check.setCheckState(Qt.CheckState.PartiallyChecked)
        self._syncing_select_all = False

    def _on_translation_changed(self, _index: int):
        self._apply_series_range()

    def _apply_series_range(self):
        if self.is_movie or not self.translations or not self.episode_rows:
            return
        index = self.translation_combo.current_index()
        if index < 0:
            return
        first, last = self.translations[index].get("series_range", (1, self.series_count))
        for n, row in self.episode_rows.items():
            in_range = first <= n <= last
            row.set_enabled(in_range)
            if not in_range and row.is_checked():
                row.set_checked(False)
        self._sync_select_all_state()

    def _on_download_clicked(self):
        selected = self.translation_combo.current_index()
        if selected < 0 or not self.translations:
            self.window.show_toast("Выберите озвучку")
            return
        translation = self.translations[selected]

        if self.is_movie:
            eps_to_download = [0]
        else:
            eps_to_download = sorted(
                n for n, row in self.episode_rows.items() if row.is_checked()
            )
            if not eps_to_download:
                self.window.show_toast("Выберите хотя бы одну серию")
                return

        folder = QFileDialog.getExistingDirectory(
            self.window, "Выберите папку для скачивания"
        )
        if not folder:
            return

        from anime_dlp.gui.qt.download_page import DownloadPage

        self.window.push_page(
            DownloadPage(
                window=self.window,
                item=self.item,
                translation_id=translation["id"],
                eps_to_download=eps_to_download,
                download_dir=Path(folder),
            )
        )
