from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from anime_dlp.gui.formatting import APP_TITLE
from anime_dlp.gui.qt.about_dialog import show_about_dialog
from anime_dlp.gui.qt.catalog_tab import CatalogTab
from anime_dlp.gui.qt.categories_tab import CategoriesTab
from anime_dlp.gui.qt.favorites_tab import FavoritesTab
from anime_dlp.gui.qt.search_tab import SearchTab
from anime_dlp.gui.qt.widgets import NavHeaderBar
from anime_dlp.gui.refresh import clear_all_caches


class HomePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = NavHeaderBar(APP_TITLE, show_back=False)
        outer.addWidget(header)

        about_button = QPushButton("ⓘ")
        about_button.setObjectName("iconButton")
        about_button.setToolTip("О программе")
        about_button.setFixedWidth(32)
        about_button.clicked.connect(self._on_about_clicked)
        header.add_start_widget(about_button)

        # Qt не центрирует QTabBar по умолчанию — оборачиваем в строку со
        # stretch-спейсерами по бокам, стандартный приём для центрирования
        # виджета естественной ширины внутри более широкого ряда.
        tab_row = QWidget()
        tab_row.setObjectName("tabRow")
        tab_row_layout = QHBoxLayout(tab_row)
        tab_row_layout.setContentsMargins(0, 6, 0, 6)
        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(False)
        self.tab_bar.setDrawBase(False)
        self.tab_bar.addTab("Главное")
        self.tab_bar.addTab("Категории")
        self.tab_bar.addTab("Избранное")
        self.tab_bar.addTab("Поиск")
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        tab_row_layout.addStretch(1)
        tab_row_layout.addWidget(self.tab_bar)
        tab_row_layout.addStretch(1)
        outer.addWidget(tab_row)

        self.stack = QStackedWidget()
        self.catalog_tab = CatalogTab(window=window)
        self.categories_tab = CategoriesTab(window=window)
        self.favorites_tab = FavoritesTab(window=window)
        self.search_tab = SearchTab(window=window)
        # Порядок виджетов обязан совпадать с порядком вкладок выше.
        self.stack.addWidget(self.catalog_tab)  # index 0 == "Главное"
        self.stack.addWidget(self.categories_tab)  # index 1 == "Категории"
        self.stack.addWidget(self.favorites_tab)  # index 2 == "Избранное"
        self.stack.addWidget(self.search_tab)  # index 3 == "Поиск"
        outer.addWidget(self.stack, 1)

        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setObjectName("iconButton")
        self.refresh_button.setToolTip("Обновить и очистить кэш")
        self.refresh_button.setFixedWidth(32)
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        header.add_end_widget(self.refresh_button)

    def _on_tab_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        # Звёздочку могли поставить на странице аниме, пока вкладка была
        # скрыта — перечитываем избранное при каждом её показе.
        if self.stack.currentWidget() is self.favorites_tab:
            self.favorites_tab.reload()

    def _on_about_clicked(self):
        show_about_dialog(self.window)

    def _on_refresh_clicked(self):
        clear_all_caches()
        current = self.stack.currentWidget()
        if current is not None:
            current.reload()
        self.window.show_toast("Кэш очищен, данные обновлены")
