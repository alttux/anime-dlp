from PyQt6.QtWidgets import QProgressBar, QScrollArea, QVBoxLayout, QWidget

from anime_dlp.core.anime_service import get_popular_anime
from anime_dlp.gui import prefetch
from anime_dlp.gui.qt.cover_card import CoverCard
from anime_dlp.gui.qt.widgets import FlowLayout
from anime_dlp.gui.qt.workers import CatalogWorker

# Насколько близко к концу прокрутки нужно оказаться, чтобы подгрузить
# следующую пачку (в пикселях значения скроллбара).
_SCROLL_THRESHOLD = 200


class CatalogTab(QWidget):
    """Сетка обложек с бесконечной прокруткой. loader — источник страниц с
    сигнатурой (cursor, limit) -> (items, next_cursor); по умолчанию это
    популярное («Главное»), страница жанра передаёт сюда get_genre_anime."""

    PAGE_SIZE = 10

    def __init__(self, window, loader=None):
        super().__init__()
        self.window = window
        self._loader = loader or get_popular_anime
        self._next_cursor: str | None = None
        self._loading = False
        self._worker: CatalogWorker | None = None
        # Растёт при reload(): ответы запросов, стартовавших до перезагрузки,
        # игнорируются, иначе они дорисовали бы старые карточки в новую сетку.
        self._generation = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        self.grid_container = QWidget()
        self.flow_layout = FlowLayout(self.grid_container, spacing=16)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.grid_container)
        outer.addWidget(self.scroll, 1)

        scrollbar = self.scroll.verticalScrollBar()
        # rangeChanged срабатывает при добавлении карточек и при resize окна
        # — этим же обработчиком дозаполняем сетку под видимую область.
        scrollbar.rangeChanged.connect(self._maybe_load_more)
        scrollbar.valueChanged.connect(self._maybe_load_more)

        self.spinner = QProgressBar()
        self.spinner.setRange(0, 0)
        self.spinner.setTextVisible(False)
        self.spinner.setFixedHeight(4)
        self.spinner.setVisible(False)
        outer.addWidget(self.spinner)

        self._load_page()

    def reload(self):
        """Полная перезагрузка сетки с первой страницы (кнопка «Обновить»)."""
        self._generation += 1
        self._loading = False
        self._next_cursor = None
        self.flow_layout.clear()
        self._load_page()

    def _load_page(self):
        if self._loading:
            return
        self._loading = True
        self.spinner.setVisible(True)
        self._worker = CatalogWorker(
            self._loader, self._next_cursor, self.PAGE_SIZE, self._generation, parent=self
        )
        self._worker.finished_page.connect(self._on_page_loaded)
        self._worker.start()

    def _on_page_loaded(self, items: list, next_cursor: str, error: str, generation: int):
        if generation != self._generation:
            return
        self._loading = False
        self.spinner.setVisible(False)
        if error:
            self.window.show_toast(f"Ошибка загрузки: {error}")
            return
        for item in items:
            self.flow_layout.addWidget(
                CoverCard(item, on_click=self._on_card_clicked, parent=self.grid_container)
            )
            prefetch.prefetch(item.get("shikimori_id"))
        self._next_cursor = next_cursor or None
        self._maybe_load_more()

    def _maybe_load_more(self, *_args):
        if self._loading or not self._next_cursor:
            return
        scrollbar = self.scroll.verticalScrollBar()
        near_bottom = (
            scrollbar.value() + scrollbar.pageStep() >= scrollbar.maximum() - _SCROLL_THRESHOLD
        )
        not_full = scrollbar.maximum() == 0
        if near_bottom or not_full:
            self._load_page()

    def _on_card_clicked(self, item: dict):
        if not item.get("shikimori_id"):
            self.window.show_toast(
                "У этого аниме нет shikimori_id, скачивание невозможно"
            )
            return
        from anime_dlp.gui.qt.details_page import DetailsPage

        self.window.push_page(DetailsPage(window=self.window, item=item))
