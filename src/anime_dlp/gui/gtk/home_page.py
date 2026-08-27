from gi.repository import Adw, GObject, Gtk

from anime_dlp.gui.formatting import APP_TITLE
from anime_dlp.gui.gtk.about_dialog import show_about_dialog
from anime_dlp.gui.gtk.catalog_tab import CatalogTab
from anime_dlp.gui.gtk.categories_tab import CategoriesTab
from anime_dlp.gui.gtk.favorites_tab import FavoritesTab
from anime_dlp.gui.gtk.search_tab import SearchTab
from anime_dlp.gui.refresh import clear_all_caches


class HomePage(Adw.NavigationPage):
    def __init__(self, window):
        super().__init__(title=APP_TITLE, tag="home")
        self.window = window

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()

        self.view_stack = Adw.ViewStack()
        switcher_title = Adw.ViewSwitcherTitle(
            stack=self.view_stack, title=APP_TITLE
        )
        header.set_title_widget(switcher_title)

        about_button = Gtk.Button(
            icon_name="help-about-symbolic",
            tooltip_text="О программе",
            css_classes=["flat"],
        )
        about_button.connect("clicked", self._on_about_clicked)
        header.pack_start(about_button)

        self.refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Обновить и очистить кэш",
            css_classes=["flat"],
        )
        self.refresh_button.connect("clicked", self._on_refresh_clicked)
        # pack_end добавляет справа налево, поэтому «Обновить» — крайняя справа.
        header.pack_end(self.refresh_button)

        self.search_tab = SearchTab(window=window)
        toolbar_view.add_top_bar(header)

        self.catalog_tab = CatalogTab(window=window)
        self.categories_tab = CategoriesTab(window=window)
        self.favorites_tab = FavoritesTab(window=window)

        catalog_page = self.view_stack.add_titled(self.catalog_tab, "catalog", "Главное")
        catalog_page.set_icon_name("go-home-symbolic")
        categories_page = self.view_stack.add_titled(
            self.categories_tab, "categories", "Категории"
        )
        categories_page.set_icon_name("view-grid-symbolic")
        favorites_page = self.view_stack.add_titled(
            self.favorites_tab, "favorites", "Избранное"
        )
        favorites_page.set_icon_name("starred-symbolic")
        search_page = self.view_stack.add_titled(self.search_tab, "search", "Поиск")
        search_page.set_icon_name("system-search-symbolic")

        # Звёздочку могли поставить на странице аниме, пока вкладка была
        # скрыта — перечитываем избранное при каждом её показе.
        self.view_stack.connect("notify::visible-child", self._on_visible_child_changed)

        # ViewSwitcherTitle показывает переключатель вкладок прямо в
        # заголовке, только пока туда помещается (title-visible=False); при
        # сужении окна он схлопывается до простого заголовка (title-visible
        # =True), и тогда нужно показать нижнюю панель-переключатель —
        # иначе обе показываются одновременно.
        switcher_bar = Adw.ViewSwitcherBar(stack=self.view_stack)
        switcher_title.bind_property(
            "title-visible",
            switcher_bar,
            "reveal",
            GObject.BindingFlags.SYNC_CREATE,
        )
        toolbar_view.add_bottom_bar(switcher_bar)

        toolbar_view.set_content(self.view_stack)
        self.set_child(toolbar_view)

    def _on_visible_child_changed(self, *_args):
        if self.view_stack.get_visible_child() is self.favorites_tab:
            self.favorites_tab.reload()

    def _on_about_clicked(self, _button):
        show_about_dialog(self.window)

    def _on_refresh_clicked(self, _button):
        clear_all_caches()
        current = self.view_stack.get_visible_child()
        if current is not None:
            current.reload()
        self.window.show_toast("Кэш очищен, данные обновлены")
