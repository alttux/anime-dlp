import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from anime_dlp.core import favorites, watch_history
from anime_dlp.gui.gtk.favorites_tab import FavoritesTab


class FavoritesGroupingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.watch_patcher = patch(
            "anime_dlp.core.watch_history._path",
            return_value=Path(self.temp_dir.name) / "watched.json",
        )
        self.fav_patcher = patch(
            "anime_dlp.core.favorites._path",
            return_value=Path(self.temp_dir.name) / "favorites.json",
        )
        self.watch_patcher.start()
        self.fav_patcher.start()
        self.addCleanup(self.watch_patcher.stop)
        self.addCleanup(self.fav_patcher.stop)
        watch_history._data = None
        favorites._items = None

    @patch("anime_dlp.gui.gtk.cover_card.CoverCard._start_poster_load")
    def test_empty_favorites(self, mock_poster):
        window = MagicMock()
        tab = FavoritesTab(window)
        self.assertEqual(tab.stack.get_visible_child_name(), "empty")

    @patch("anime_dlp.gui.gtk.cover_card.CoverCard._start_poster_load")
    def test_grouped_sections(self, mock_poster):
        # 1. Завершённый тайтл
        item_done = {"shikimori_id": "done_1", "title": "Done Anime", "episodes_count": 2}
        watch_history.mark_watched("done_1", 1, series_count=2)
        watch_history.mark_watched("done_1", 2, series_count=2)

        # 2. Начатый тайтл
        item_prog = {"shikimori_id": "prog_1", "title": "In Progress Anime", "episodes_count": 12}
        watch_history.mark_watched("prog_1", 1, series_count=12)

        # 3. Не начатый тайтл
        item_new = {"shikimori_id": "new_1", "title": "New Anime", "episodes_count": 12}

        favorites.toggle(item_done)
        favorites.toggle(item_prog)
        favorites.toggle(item_new)

        window = MagicMock()
        tab = FavoritesTab(window)
        tab.reload()

        self.assertEqual(tab.stack.get_visible_child_name(), "items")

        # Проверяем дочерние элементы в groups_box:
        # Должны идти чередуясь: Header ("Просмотрено"), FlowBox, Header ("Начато"), FlowBox, Header ("Не начато"), FlowBox
        children = []
        child = tab.groups_box.get_first_child()
        while child is not None:
            children.append(child)
            child = child.get_next_sibling()

        self.assertEqual(len(children), 6)  # 3 секции * 2 (header + flowbox)

        # Проверяем тексты заголовков
        # Внутри header: Image, Label(title), Label(count), Separator
        header_titles = []
        for i in (0, 2, 4):
            header_box = children[i]
            # Вторым элементом идёт Label заголовка
            label = header_box.get_first_child().get_next_sibling()
            header_titles.append(label.get_label())

        self.assertEqual(
            header_titles,
            ["Просмотрено", "Начато", "Не начато"],
        )


if __name__ == "__main__":
    unittest.main()
