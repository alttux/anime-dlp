from gi.repository import Adw

from anime_dlp.gui.gtk.catalog_tab import CatalogTab
from anime_dlp.gui.gtk.search_tab import SearchTab


class HomePage(Adw.NavigationPage):
    def __init__(self, window):
        super().__init__(title="Anime Downloader", tag="home")
        self.window = window

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()

        self.view_stack = Adw.ViewStack()
        switcher_title = Adw.ViewSwitcherTitle(
            stack=self.view_stack, title="Anime Downloader"
        )
        header.set_title_widget(switcher_title)

        self.search_tab = SearchTab(window=window)
        interface_button = self.search_tab.build_interface_button()
        if interface_button is not None:
            header.pack_end(interface_button)
        toolbar_view.add_top_bar(header)

        self.catalog_tab = CatalogTab(window=window)

        catalog_page = self.view_stack.add_titled(self.catalog_tab, "catalog", "Главное")
        catalog_page.set_icon_name("go-home-symbolic")
        search_page = self.view_stack.add_titled(self.search_tab, "search", "Поиск")
        search_page.set_icon_name("system-search-symbolic")

        switcher_bar = Adw.ViewSwitcherBar(stack=self.view_stack, reveal=True)
        toolbar_view.add_bottom_bar(switcher_bar)

        toolbar_view.set_content(self.view_stack)
        self.set_child(toolbar_view)
