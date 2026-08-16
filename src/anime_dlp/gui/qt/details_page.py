from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from anime_dlp.core.anime_info import extract_anime_info, has_any_info
from anime_dlp.gui.qt.widgets import (
    ActionRow,
    ComboRow,
    ExpanderRow,
    FlowLayout,
    NavHeaderBar,
    PreferencesGroup,
    SpinRow,
)
from anime_dlp.gui.qt.workers import AnimeInfoWorker, PosterWorker

POSTER_WIDTH = 200
POSTER_HEIGHT = 280


def _suffix_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("heading")
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    label.setMaximumWidth(200)
    return label


class DetailsPage(QWidget):
    def __init__(self, window, item: dict):
        super().__init__()
        self.window = window
        self.item = item
        self.translations: list[dict] = []
        self.series_count = None
        self.is_movie = False

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
        title_label = QLabel(self.item.get("title", "Anime"))
        title_label.setObjectName("title1")
        title_label.setWordWrap(True)

        header_row = QHBoxLayout()
        header_row.setSpacing(18)
        header_row.addWidget(self.poster_label)
        header_row.addWidget(title_label, 1)
        self.form_box.addLayout(header_row)

        if not self.poster_label.pixmap().isNull():
            self.poster_label.setVisible(True)

        info_group = self._build_info_group()
        translation_group = PreferencesGroup(title="Озвучка")
        self.translation_combo = ComboRow("Вариант озвучки")
        self.translation_combo.set_items(
            [f"{t['type']} — {t['name']}" for t in self.translations]
        )
        translation_group.add(self.translation_combo)

        self.is_movie = self.series_count == 0 or self.series_count is None

        episodes_group = PreferencesGroup(title="Серии")
        if self.is_movie:
            row = ActionRow(title="Фильм", subtitle="Определено как фильм")
            episodes_group.add(row)
        else:
            self.single_episode_radio = QRadioButton()
            self.range_episode_radio = QRadioButton()
            self.all_episodes_radio = QRadioButton()
            self.single_episode_radio.setChecked(True)

            self._episode_mode_group = QButtonGroup(self)
            self._episode_mode_group.addButton(self.single_episode_radio)
            self._episode_mode_group.addButton(self.range_episode_radio)
            self._episode_mode_group.addButton(self.all_episodes_radio)

            self.episode_spin = SpinRow("Номер серии", 1, self.series_count, 1)

            self.range_from_spin = SpinRow("Серия от", 1, self.series_count, 1)
            self.range_to_spin = SpinRow("Серия до", 1, self.series_count, self.series_count)

            for radio in (
                self.single_episode_radio,
                self.range_episode_radio,
                self.all_episodes_radio,
            ):
                radio.toggled.connect(self._on_episode_mode_toggled)

            single_row = ActionRow(title="Одна серия")
            single_row.add_prefix(self.single_episode_radio)
            episodes_group.add(single_row)
            episodes_group.add(self.episode_spin)

            range_row = ActionRow(title="Диапазон серий")
            range_row.add_prefix(self.range_episode_radio)
            episodes_group.add(range_row)
            episodes_group.add(self.range_from_spin)
            episodes_group.add(self.range_to_spin)

            all_row = ActionRow(title="Все серии")
            all_row.add_prefix(self.all_episodes_radio)
            episodes_group.add(all_row)

            self._on_episode_mode_toggled()

        flow_container = QWidget()
        sections_flow = FlowLayout(flow_container, spacing=18, max_columns=3)

        if info_group is not None:
            info_group.setMinimumWidth(280)
            sections_flow.addWidget(info_group)

        translation_group.setMinimumWidth(280)
        sections_flow.addWidget(translation_group)

        episodes_group.setMinimumWidth(280)
        sections_flow.addWidget(episodes_group)

        self.form_box.addWidget(flow_container)

    def _build_info_group(self) -> PreferencesGroup | None:
        info = extract_anime_info(self.item)
        if not has_any_info(info):
            return None

        group = PreferencesGroup(title="Об аниме")

        if info.status:
            row = ActionRow(title="Статус")
            row.add_suffix(_suffix_label(info.status))
            group.add(row)

        if info.episodes_total:
            if info.episodes_aired and info.episodes_aired != info.episodes_total:
                episodes = f"{info.episodes_aired}/{info.episodes_total}"
            else:
                episodes = str(info.episodes_total)
            row = ActionRow(title="Эпизоды")
            row.add_suffix(_suffix_label(episodes))
            group.add(row)
        elif info.episodes_aired:
            row = ActionRow(title="Эпизоды")
            row.add_suffix(_suffix_label(str(info.episodes_aired)))
            group.add(row)

        if info.score:
            rating = str(info.score)
            if info.votes:
                rating += f" ({info.votes} голосов)"
            row = ActionRow(title="Рейтинг")
            row.add_suffix(_suffix_label(rating))
            group.add(row)

        if info.genres:
            row = ActionRow(title="Жанры")
            row.add_suffix(_suffix_label(", ".join(info.genres)))
            group.add(row)

        if info.studios:
            row = ActionRow(title="Студия")
            row.add_suffix(_suffix_label(", ".join(info.studios)))
            group.add(row)

        if info.description:
            expander = ExpanderRow(title="Описание")
            expander.set_expanded(False)
            label = QLabel(info.description)
            label.setWordWrap(True)
            expander.add_row(label)
            group.add(expander)

        return group

    def _on_episode_mode_toggled(self, *_args):
        if hasattr(self, "episode_spin"):
            self.episode_spin.setEnabled(self.single_episode_radio.isChecked())
        if hasattr(self, "range_from_spin"):
            is_range = self.range_episode_radio.isChecked()
            self.range_from_spin.setEnabled(is_range)
            self.range_to_spin.setEnabled(is_range)

    def _on_download_clicked(self):
        selected = self.translation_combo.current_index()
        if selected < 0 or not self.translations:
            self.window.show_toast("Выберите озвучку")
            return
        translation = self.translations[selected]

        if self.is_movie:
            eps_to_download = [0]
        elif self.all_episodes_radio.isChecked():
            eps_to_download = list(range(1, self.series_count + 1))
        elif self.range_episode_radio.isChecked():
            start = self.range_from_spin.value()
            end = self.range_to_spin.value()
            if start > end:
                self.window.show_toast("«Серия от» не может быть больше «Серия до»")
                return
            eps_to_download = list(range(start, end + 1))
        else:
            eps_to_download = [self.episode_spin.value()]

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
