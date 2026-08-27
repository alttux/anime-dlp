from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from anime_dlp.core.anime_service import GENRES
from anime_dlp.gui.genre_posters import get_genre_poster
from anime_dlp.gui.qt.cover_card import CoverCard
from anime_dlp.gui.qt.widgets import FlowLayout


class CategoriesTab(QWidget):
    """Сетка жанров. Обложки — статичные постеры, сгенерированные нейросетью
    под смысл жанра (gui/genre_posters.py), а не топ-1 аниме жанра, поэтому
    карточки собираются сразу целиком, без фоновой подгрузки."""

    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        self.grid_container = QWidget()
        self.flow_layout = FlowLayout(self.grid_container, spacing=16)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.grid_container)
        outer.addWidget(self.scroll, 1)

        self._build_cards()

    def reload(self):
        """Пересобирает карточки (кнопка «Обновить») — постеры статичные, так
        что достаточно просто перерисовать сетку."""
        self.flow_layout.clear()
        self._build_cards()

    def _build_cards(self):
        for genre in GENRES:
            card = CoverCard(
                None,
                on_click=self._make_click_handler(genre),
                title=genre,
                parent=self.grid_container,
            )
            card.set_static_cover(get_genre_poster(genre))
            self.flow_layout.addWidget(card)

    def _make_click_handler(self, genre: str):
        # У карточки жанра нет своей записи аниме — клик открывает сетку жанра.
        def on_click(_item):
            from anime_dlp.gui.qt.genre_page import GenrePage

            self.window.push_page(GenrePage(window=self.window, genre=genre))

        return on_click
