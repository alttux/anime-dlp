from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from anime_dlp.core.anime_info import extract_anime_info
from anime_dlp.gui.qt.workers import PosterWorker

_WIDTH = 140
_HEIGHT = 200


class CoverCard(QFrame):
    def __init__(self, item: dict, on_click, parent=None):
        super().__init__(parent)
        self.setObjectName("coverCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._item = item
        self._on_click = on_click
        self.setFixedWidth(_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.poster_label = QLabel()
        self.poster_label.setFixedSize(_WIDTH, _HEIGHT)
        self.poster_label.setScaledContents(False)
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet(
            "background: palette(alternate-base); border-radius: 6px;"
        )
        layout.addWidget(self.poster_label)

        title_label = QLabel(item.get("title", "Unknown"))
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setMaximumHeight(40)
        layout.addWidget(title_label)

        self._poster_worker: PosterWorker | None = None
        poster_url = extract_anime_info(item).poster_url
        if poster_url:
            self._poster_worker = PosterWorker(poster_url, parent=self)
            self._poster_worker.finished_poster.connect(self._on_poster_loaded)
            self._poster_worker.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self._item)
        super().mousePressEvent(event)

    def _on_poster_loaded(self, data: bytes, error: str):
        if error or not data:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        pixmap = pixmap.scaled(
            _WIDTH,
            _HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.poster_label.setPixmap(pixmap)
