from PyQt6.QtWidgets import QHBoxLayout, QStackedWidget, QTabBar, QVBoxLayout, QWidget

from anime_dlp.gui.qt.catalog_tab import CatalogTab
from anime_dlp.gui.qt.search_tab import SearchTab
from anime_dlp.gui.qt.widgets import NavHeaderBar


class HomePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = NavHeaderBar("Anime Downloader", show_back=False)
        outer.addWidget(header)

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
        self.tab_bar.addTab("Поиск")
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        tab_row_layout.addStretch(1)
        tab_row_layout.addWidget(self.tab_bar)
        tab_row_layout.addStretch(1)
        outer.addWidget(tab_row)

        self.stack = QStackedWidget()
        self.catalog_tab = CatalogTab(window=window)
        self.search_tab = SearchTab(window=window)
        self.stack.addWidget(self.catalog_tab)  # index 0 == "Главное"
        self.stack.addWidget(self.search_tab)  # index 1 == "Поиск"
        outer.addWidget(self.stack, 1)

        interface_button = self.search_tab.build_interface_button()
        if interface_button is not None:
            header.add_end_widget(interface_button)

    def _on_tab_changed(self, index: int):
        self.stack.setCurrentIndex(index)
