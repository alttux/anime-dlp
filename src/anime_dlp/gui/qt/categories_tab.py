from PyQt6.QtWidgets import QProgressBar, QScrollArea, QVBoxLayout, QWidget

from anime_dlp.core.anime_service import GENRES
from anime_dlp.gui.qt.cover_card import CoverCard
from anime_dlp.gui.qt.widgets import FlowLayout
from anime_dlp.gui.qt.workers import GenreCoversWorker


class CategoriesTab(QWidget):
    """Сетка жанров. Карточки создаются сразу все и в фиксированном порядке —
    так лэйаут не прыгает, — а обложки (топ-1 аниме жанра) подставляются в них
    по мере готовности фоновой загрузки."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._generation = 0
        self._cards: dict[str, CoverCard] = {}
        self._worker: GenreCoversWorker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        self.grid_container = QWidget()
        self.flow_layout = FlowLayout(self.grid_container, spacing=16)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.grid_container)
        outer.addWidget(self.scroll, 1)

        self.spinner = QProgressBar()
        self.spinner.setRange(0, 0)
        self.spinner.setTextVisible(False)
        self.spinner.setFixedHeight(4)
        self.spinner.setVisible(False)
        outer.addWidget(self.spinner)

        self._build_cards()

    def reload(self):
        """Пересобирает карточки и заново ищет обложки (кнопка «Обновить»)."""
        self._generation += 1
        self.flow_layout.clear()
        self._build_cards()

    def _build_cards(self):
        self._cards = {}
        for genre in GENRES:
            card = CoverCard(
                None,
                on_click=self._make_click_handler(genre),
                title=genre,
                parent=self.grid_container,
            )
            self._cards[genre] = card
            self.flow_layout.addWidget(card)

        self.spinner.setVisible(True)
        self._worker = GenreCoversWorker(GENRES, self._generation, parent=self)
        self._worker.cover_ready.connect(self._on_cover_loaded)
        self._worker.finished.connect(self._on_covers_done)
        self._worker.start()

    def _on_cover_loaded(self, genre: str, item: dict, generation: int):
        if generation != self._generation:
            return
        card = self._cards.get(genre)
        if card is not None:
            card.set_item(item)

    def _on_covers_done(self):
        self.spinner.setVisible(False)

    def _make_click_handler(self, genre: str):
        # У карточки жанра нет своей записи аниме — клик открывает сетку жанра.
        def on_click(_item):
            from anime_dlp.gui.qt.genre_page import GenrePage

            self.window.push_page(GenrePage(window=self.window, genre=genre))

        return on_click
