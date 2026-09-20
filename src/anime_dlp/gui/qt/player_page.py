from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from anime_dlp.core.playback import PlaybackSources
from anime_dlp.gui.qt.widgets import NavHeaderBar
from anime_dlp.gui.qt.workers import PlaybackWorker


def _format_time(milliseconds: int) -> str:
    seconds = max(0, milliseconds // 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class PlayerPage(QWidget):
    """Kodik HLS player backed by QtMultimedia."""

    def __init__(
        self,
        window,
        item: dict,
        translation: dict,
        episode: int,
        series_range: tuple[int, int],
    ):
        super().__init__()
        self.window = window
        self.item = item
        self.translation = translation
        self.episode = episode
        self.series_range = series_range
        self.sources: PlaybackSources | None = None
        self.current_quality: int | None = None
        self._load_generation = 0
        self._pending_position = 0
        self._resume_after_load = True
        self._pending_media_start = False
        self._quality_sync = False
        self._fullscreen = False
        self._window_state_before_fullscreen = window.windowState()
        self._disposed = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = NavHeaderBar(item.get("title", "Anime"), show_back=True)
        header.back_clicked.connect(self.window.pop_page)
        outer.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 12)
        content_layout.setSpacing(8)

        self.episode_label = QLabel()
        self.episode_label.setObjectName("heading")
        content_layout.addWidget(self.episode_label)

        self.video = QVideoWidget()
        self.video.setMinimumSize(480, 270)
        content_layout.addWidget(self.video, 1)

        self.status = QLabel("Получение ссылки Kodik...")
        self.status.setObjectName("dimLabel")
        content_layout.addWidget(self.status)

        timeline = QHBoxLayout()
        self.elapsed_label = QLabel("0:00")
        timeline.addWidget(self.elapsed_label)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        timeline.addWidget(self.seek_slider, 1)
        self.duration_label = QLabel("0:00")
        timeline.addWidget(self.duration_label)
        content_layout.addLayout(timeline)

        controls = QHBoxLayout()
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previous_button = self._media_button(
            QStyle.StandardPixmap.SP_MediaSkipBackward,
            "Предыдущая серия",
            self._on_previous,
        )
        controls.addWidget(self.previous_button)
        controls.addWidget(
            self._media_button(
                QStyle.StandardPixmap.SP_MediaSeekBackward,
                "Назад на 5 секунд",
                self._on_rewind,
            )
        )
        self.play_button = self._media_button(
            QStyle.StandardPixmap.SP_MediaPlay,
            "Воспроизвести",
            self._on_play_pause,
        )
        self.play_button.setEnabled(False)
        controls.addWidget(self.play_button)
        controls.addWidget(
            self._media_button(
                QStyle.StandardPixmap.SP_MediaSeekForward,
                "Вперёд на 5 секунд",
                self._on_forward,
            )
        )
        self.next_button = self._media_button(
            QStyle.StandardPixmap.SP_MediaSkipForward,
            "Следующая серия",
            self._on_next,
        )
        controls.addWidget(self.next_button)

        self.quality_combo = QComboBox()
        self.quality_combo.setToolTip("Качество видео")
        self.quality_combo.setEnabled(False)
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)
        controls.addWidget(self.quality_combo)

        self.fullscreen_button = self._media_button(
            QStyle.StandardPixmap.SP_TitleBarMaxButton,
            "Полноэкранный режим",
            self._on_fullscreen,
        )
        controls.addWidget(self.fullscreen_button)
        content_layout.addLayout(controls)
        outer.addWidget(content, 1)

        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.errorOccurred.connect(self._on_player_error)

        self._load_episode(episode, autoplay=True)

    def _media_button(self, icon, tooltip: str, callback) -> QPushButton:
        button = QPushButton()
        button.setObjectName("iconButton")
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        button.clicked.connect(callback)
        return button

    def _load_episode(self, episode: int, autoplay: bool):
        self._load_generation += 1
        generation = self._load_generation
        self.episode = episode
        self._resume_after_load = autoplay
        self._pending_position = 0
        self._pending_media_start = False
        self.player.stop()
        self.play_button.setEnabled(False)
        self.seek_slider.setEnabled(False)
        self.status.setText("Получение ссылки Kodik...")
        self.episode_label.setText(
            self.item.get("title", "Anime")
            if episode == 0
            else f"{self.item.get('title', 'Anime')} — серия {episode}"
        )
        self._sync_episode_buttons()

        worker = PlaybackWorker(
            str(self.item["shikimori_id"]),
            episode,
            str(self.translation["id"]),
            generation,
        )
        worker.finished_sources.connect(self._on_sources_loaded)
        worker.start()

    def _on_sources_loaded(self, sources, error: str, generation: int):
        if self._disposed or generation != self._load_generation:
            return
        if error or sources is None:
            self.status.setText(f"Не удалось открыть видео: {error}")
            self.window.show_toast(f"Ошибка плеера: {error}")
            return

        previous_quality = self.current_quality
        self.sources = sources
        quality = (
            previous_quality
            if previous_quality in sources.qualities
            else sources.default_quality
        )
        self._quality_sync = True
        self.quality_combo.clear()
        self.quality_combo.addItems([f"{q}p" for q in sources.qualities])
        self.quality_combo.setCurrentIndex(sources.qualities.index(quality))
        self._quality_sync = False
        self.quality_combo.setEnabled(True)
        self._set_media_source(quality, 0, self._resume_after_load)

    def _set_media_source(self, quality: int, position: int, autoplay: bool):
        if self.sources is None:
            return
        self.current_quality = quality
        self._pending_position = position
        self._resume_after_load = autoplay
        self._pending_media_start = True
        self.status.setText(f"Загрузка {quality}p...")
        self.play_button.setEnabled(False)
        self.player.setSource(QUrl(self.sources.hls_url(quality)))

    def _on_media_status_changed(self, status):
        ready_statuses = {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        }
        if status in ready_statuses and self._pending_media_start:
            self._pending_media_start = False
            if self._pending_position:
                self.player.setPosition(self._pending_position)
            self.play_button.setEnabled(True)
            self.status.setText("")
            if self._resume_after_load:
                self.player.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.episode < self.series_range[1]:
                self._load_episode(self.episode + 1, autoplay=True)

    def _on_position_changed(self, position: int):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)
        self.elapsed_label.setText(_format_time(position))

    def _on_duration_changed(self, duration: int):
        self.seek_slider.setRange(0, max(0, duration))
        self.seek_slider.setEnabled(duration > 0 and self.player.isSeekable())
        self.duration_label.setText(_format_time(duration))

    def _on_seek_moved(self, position: int):
        if self.player.isSeekable():
            self.player.setPosition(position)

    def _seek_relative(self, milliseconds: int):
        if not self.player.isSeekable():
            return
        position = self.player.position() + milliseconds
        self.player.setPosition(max(0, min(position, self.player.duration())))

    def _on_rewind(self):
        self._seek_relative(-5000)

    def _on_forward(self):
        self._seek_relative(5000)

    def _on_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_playback_state_changed(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        icon = (
            QStyle.StandardPixmap.SP_MediaPause
            if playing
            else QStyle.StandardPixmap.SP_MediaPlay
        )
        self.play_button.setIcon(self.style().standardIcon(icon))
        self.play_button.setToolTip("Пауза" if playing else "Воспроизвести")

    def _on_player_error(self, _error, message: str):
        if message:
            self.status.setText(f"Ошибка воспроизведения: {message}")

    def _on_quality_changed(self, index: int):
        if self._quality_sync or self.sources is None or index < 0:
            return
        quality = self.sources.qualities[index]
        if quality == self.current_quality:
            return
        self._set_media_source(
            quality,
            self.player.position(),
            self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
        )

    def _sync_episode_buttons(self):
        first, last = self.series_range
        self.previous_button.setEnabled(self.episode > first)
        self.next_button.setEnabled(self.episode < last)

    def _on_previous(self):
        if self.episode > self.series_range[0]:
            self._load_episode(self.episode - 1, autoplay=True)

    def _on_next(self):
        if self.episode < self.series_range[1]:
            self._load_episode(self.episode + 1, autoplay=True)

    def _on_fullscreen(self):
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self._window_state_before_fullscreen = self.window.windowState()
            self.window.showFullScreen()
            icon = QStyle.StandardPixmap.SP_TitleBarNormalButton
            tooltip = "Выйти из полноэкранного режима"
        else:
            self.window.setWindowState(self._window_state_before_fullscreen)
            self.window.show()
            icon = QStyle.StandardPixmap.SP_TitleBarMaxButton
            tooltip = "Полноэкранный режим"
        self.fullscreen_button.setIcon(self.style().standardIcon(icon))
        self.fullscreen_button.setToolTip(tooltip)

    def cleanup(self):
        self._disposed = True
        self._load_generation += 1
        self.player.stop()
        self.player.setSource(QUrl())
        if self._fullscreen:
            self.window.setWindowState(self._window_state_before_fullscreen)
            self.window.show()
            self._fullscreen = False
