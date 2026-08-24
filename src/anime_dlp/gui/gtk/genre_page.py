from gi.repository import Adw

from anime_dlp.core.anime_service import get_genre_anime
from anime_dlp.gui.gtk.catalog_tab import CatalogTab


class GenrePage(Adw.NavigationPage):
    """Сетка аниме одного жанра — тот же CatalogTab, что и на «Главном»,
    только с другим источником страниц."""

    def __init__(self, window, genre: str):
        super().__init__(title=genre, tag="genre")
        self.window = window
        self.genre = genre

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())
        toolbar_view.set_content(
            CatalogTab(
                window=window,
                loader=lambda cursor, limit: get_genre_anime(genre, cursor, limit),
            )
        )
        self.set_child(toolbar_view)
