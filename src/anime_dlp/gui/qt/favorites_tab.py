from PyQt6.QtWidgets import QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from anime_dlp.core import favorites
from anime_dlp.gui.qt.cover_card import CoverCard
from anime_dlp.gui.qt.widgets import FlowLayout, StatusPage


class FavoritesTab(QWidget):
    """Сетка аниме, отмеченных звёздочкой на странице аниме. Данные лежат на
    диске полными записями, поэтому вкладка рисуется без единого запроса."""

    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        self.stack = QStackedWidget()

        self.empty_page = StatusPage(
            icon_text="★",
            title="Избранное пусто",
            description="Отмечайте аниме звёздочкой на странице аниме",
        )
        self.stack.addWidget(self.empty_page)

        self.grid_container = QWidget()
        self.flow_layout = FlowLayout(self.grid_container, spacing=16)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.grid_container)
        self.stack.addWidget(self.scroll)

        outer.addWidget(self.stack, 1)
        self.reload()

    def reload(self):
        """Перечитывает избранное с диска и перестраивает сетку. Вызывается
        при каждом показе вкладки — звёздочку могли поставить только что."""
        self.flow_layout.clear()

        items = favorites.load()
        for item in items:
            self.flow_layout.addWidget(
                CoverCard(item, on_click=self._on_card_clicked, parent=self.grid_container)
            )

        self.stack.setCurrentWidget(self.scroll if items else self.empty_page)

    def _on_card_clicked(self, item: dict):
        from anime_dlp.gui.qt.details_page import DetailsPage

        self.window.push_page(DetailsPage(window=self.window, item=item))
