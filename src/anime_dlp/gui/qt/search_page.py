from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from anime_dlp.gui.qt.widgets import ActionRow, NavHeaderBar, StatusPage
from anime_dlp.gui.qt.workers import SearchWorker
from anime_dlp.labels import TYPE_MAP

DEBOUNCE_MS = 300


class SearchPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._worker: SearchWorker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(NavHeaderBar("Anime Downloader", show_back=False))

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(12)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Введите название аниме")
        self.search_entry.setClearButtonEnabled(True)
        self.search_entry.textChanged.connect(self._on_text_changed)
        body_layout.addWidget(self.search_entry)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._trigger_search)

        self.stack = QStackedWidget()

        self.empty_page = StatusPage(
            icon_text="🔍",
            title="Поиск аниме",
            description="Введите название, чтобы увидеть варианты",
        )
        self.stack.addWidget(self.empty_page)

        loading_page = QWidget()
        loading_layout = QVBoxLayout(loading_page)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner = QProgressBar()
        spinner.setRange(0, 0)
        spinner.setFixedWidth(200)
        spinner.setTextVisible(False)
        loading_layout.addWidget(spinner)
        self.stack.addWidget(loading_page)

        self.not_found_page = StatusPage(icon_text="❓", title="Ничего не найдено")
        self.stack.addWidget(self.not_found_page)

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(1)
        self.results_layout.addStretch(1)
        results_scroll = QScrollArea()
        results_scroll.setWidgetResizable(True)
        results_scroll.setWidget(self.results_container)
        self.stack.addWidget(results_scroll)

        self.stack.setCurrentWidget(self.empty_page)
        body_layout.addWidget(self.stack, 1)

        outer.addWidget(body, 1)

    def _on_text_changed(self, text: str):
        self._debounce_timer.stop()
        text = text.strip()
        if not text:
            self.stack.setCurrentWidget(self.empty_page)
            return
        self._debounce_timer.start(DEBOUNCE_MS)

    def _trigger_search(self):
        text = self.search_entry.text().strip()
        if not text:
            self.stack.setCurrentWidget(self.empty_page)
            return
        self.stack.setCurrentIndex(1)  # loading
        self._worker = SearchWorker(text, parent=self)
        self._worker.finished_search.connect(self._on_search_results)
        self._worker.start()

    def _on_search_results(self, query: str, items: list, error: str):
        if query != self.search_entry.text().strip():
            return

        if error:
            self.window.show_toast(f"Ошибка поиска: {error}")
            self.stack.setCurrentWidget(self.empty_page)
            return

        if not items:
            self.stack.setCurrentWidget(self.not_found_page)
            return

        while self.results_layout.count() > 1:
            item_widget = self.results_layout.takeAt(0).widget()
            if item_widget is not None:
                item_widget.deleteLater()

        for item in items:
            raw_type = item.get("type", "")
            anime_type = TYPE_MAP.get(raw_type, raw_type)
            year = item.get("year", "")
            row = ActionRow(
                title=item.get("title", "Unknown"),
                subtitle=f"{year} · {anime_type}",
                activatable=True,
            )
            row.add_suffix(QLabel("›"))
            row.clicked.connect(lambda item=item: self._on_result_activated(item))
            self.results_layout.insertWidget(self.results_layout.count() - 1, row)

        self.stack.setCurrentIndex(3)  # results

    def _on_result_activated(self, item: dict):
        if not item.get("shikimori_id"):
            self.window.show_toast(
                "У этого аниме нет shikimori_id, скачивание невозможно"
            )
            return
        from anime_dlp.gui.qt.details_page import DetailsPage

        self.window.push_page(DetailsPage(window=self.window, item=item))
