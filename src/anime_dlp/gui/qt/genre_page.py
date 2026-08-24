from PyQt6.QtWidgets import QVBoxLayout, QWidget

from anime_dlp.core.anime_service import get_genre_anime
from anime_dlp.gui.qt.catalog_tab import CatalogTab
from anime_dlp.gui.qt.widgets import NavHeaderBar


class GenrePage(QWidget):
    """Сетка аниме одного жанра — тот же CatalogTab, что и на «Главном»,
    только с другим источником страниц."""

    def __init__(self, window, genre: str):
        super().__init__()
        self.window = window
        self.genre = genre

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = NavHeaderBar(genre, show_back=True)
        header.back_clicked.connect(self.window.pop_page)
        outer.addWidget(header)

        outer.addWidget(
            CatalogTab(
                window=window,
                loader=lambda cursor, limit: get_genre_anime(genre, cursor, limit),
            ),
            1,
        )
