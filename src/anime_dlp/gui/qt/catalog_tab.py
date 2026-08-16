from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget

from anime_dlp.gui.qt.cover_card import CoverCard
from anime_dlp.gui.qt.widgets import FlowLayout
from anime_dlp.gui.qt.workers import PopularWorker


class CatalogTab(QWidget):
    PAGE_SIZE = 10

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._next_cursor: str | None = None
        self._loading = False
        self._worker: PopularWorker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        self.grid_container = QWidget()
        self.flow_layout = FlowLayout(self.grid_container, spacing=16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_container)
        outer.addWidget(scroll, 1)

        self.load_more_button = QPushButton("Прогрузить ещё")
        self.load_more_button.setObjectName("accentButton")
        self.load_more_button.clicked.connect(self._load_page)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.load_more_button)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        self._load_page()

    def _load_page(self):
        if self._loading:
            return
        self._loading = True
        self.load_more_button.setEnabled(False)
        self._worker = PopularWorker(self._next_cursor, self.PAGE_SIZE, parent=self)
        self._worker.finished_popular.connect(self._on_page_loaded)
        self._worker.start()

    def _on_page_loaded(self, items: list, next_cursor: str, has_next: bool, error: str):
        self._loading = False
        self.load_more_button.setEnabled(True)
        if error:
            self.window.show_toast(f"Ошибка загрузки: {error}")
            return
        for item in items:
            self.flow_layout.addWidget(
                CoverCard(item, on_click=self._on_card_clicked, parent=self.grid_container)
            )
        self._next_cursor = next_cursor or None
        self.load_more_button.setVisible(has_next)

    def _on_card_clicked(self, item: dict):
        if not item.get("shikimori_id"):
            self.window.show_toast(
                "У этого аниме нет shikimori_id, скачивание невозможно"
            )
            return
        from anime_dlp.gui.qt.details_page import DetailsPage

        self.window.push_page(DetailsPage(window=self.window, item=item))
