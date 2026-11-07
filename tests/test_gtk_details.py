import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from anime_dlp.core import translations, watch_history
from anime_dlp.gui.gtk.details_page import DetailsPage


class GtkDetailsPageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.watch_patcher = patch(
            "anime_dlp.core.watch_history._path",
            return_value=Path(self.temp_dir.name) / "watched.json",
        )
        self.trans_patcher = patch(
            "anime_dlp.core.translations._path",
            return_value=Path(self.temp_dir.name) / "translations.json",
        )
        self.watch_patcher.start()
        self.trans_patcher.start()
        self.addCleanup(self.watch_patcher.stop)
        self.addCleanup(self.trans_patcher.stop)
        watch_history._data = None
        translations._data = None

    @patch("anime_dlp.gui.gtk.details_page.fetch_image_cached")
    @patch("anime_dlp.gui.gtk.details_page.prefetch.get_or_fetch")
    def test_next_play_episode_logic(self, mock_prefetch, mock_fetch_image):
        mock_prefetch.return_value = {
            "series_count": 12,
            "translations": [
                {"id": "610", "type": "Озвучка", "name": "AniLibria.TV", "series_range": [1, 12]},
            ],
        }
        item = {"shikimori_id": "test_sid", "title": "Test Anime"}
        window = MagicMock()

        page = DetailsPage(window=window, item=item)
        # Симулируем успешную загрузку информации
        page._on_info_loaded(mock_prefetch.return_value, None)

        # 1. Просмотр не начат: должен вернуть 1
        self.assertEqual(page._get_next_play_episode(), 1)

        # 2. Просмотрена 1-я серия: должен вернуть 2
        watch_history.mark_watched("test_sid", episode=1, series_count=12)
        self.assertEqual(page._get_next_play_episode(), 2)

        # 3. Просмотрены все серии: должен вернуть 1
        for ep in range(1, 13):
            watch_history.mark_watched("test_sid", episode=ep, series_count=12)
        self.assertEqual(page._get_next_play_episode(), 1)

    @patch("anime_dlp.gui.gtk.details_page.fetch_image_cached")
    @patch("anime_dlp.gui.gtk.details_page.prefetch.get_or_fetch")
    def test_next_play_episode_for_movie(self, mock_prefetch, mock_fetch_image):
        mock_prefetch.return_value = {
            "series_count": 0,
            "translations": [
                {"id": "610", "type": "Озвучка", "name": "AniLibria.TV", "series_range": [0, 0]},
            ],
        }
        item = {"shikimori_id": "movie_sid", "title": "Movie Anime"}
        window = MagicMock()

        page = DetailsPage(window=window, item=item)
        page._on_info_loaded(mock_prefetch.return_value, None)
        self.assertEqual(page._get_next_play_episode(), 0)

    @patch("anime_dlp.gui.gtk.details_page.fetch_image_cached")
    @patch("anime_dlp.gui.gtk.details_page.prefetch.get_or_fetch")
    def test_restores_and_saves_selected_translation(self, mock_prefetch, mock_fetch_image):
        # Предварительно сохраняем выбор AniDUB (id=609)
        translations.save_selected_translation("test_trans_sid", {"id": "609", "name": "AniDUB"})

        mock_prefetch.return_value = {
            "series_count": 12,
            "translations": [
                {"id": "610", "type": "Озвучка", "name": "AniLibria.TV", "series_range": [1, 12]},
                {"id": "609", "type": "Озвучка", "name": "AniDUB", "series_range": [1, 12]},
            ],
        }
        item = {"shikimori_id": "test_trans_sid", "title": "Test Translation"}
        window = MagicMock()

        page = DetailsPage(window=window, item=item)
        page._on_info_loaded(mock_prefetch.return_value, None)

        # Озвучка должна автоматически восстановиться на индекс 1 (AniDUB)
        self.assertEqual(page.translation_combo.get_selected(), 1)

    @patch("anime_dlp.gui.gtk.details_page.fetch_image_cached")
    @patch("anime_dlp.gui.gtk.details_page.prefetch.get_or_fetch")
    def test_shikimori_link_in_header(self, mock_prefetch, mock_fetch_image):
        from anime_dlp.core.anime_info import extract_anime_info

        item = {"shikimori_id": "5114", "title": "Fullmetal Alchemist"}
        window = MagicMock()
        page = DetailsPage(window=window, item=item)
        info = extract_anime_info(page.item)
        header_box = page._build_header(info)

        # header_box contains poster_picture, then text_box, whose first child is title_row
        poster = header_box.get_first_child()
        text_box = poster.get_next_sibling()
        title_row = text_box.get_first_child()
        self.assertIsNotNone(title_row)

        # Find LinkButton among children
        link_btns = []
        child = title_row.get_first_child()
        while child:
            if isinstance(child, Gtk.LinkButton):
                link_btns.append(child)
            child = child.get_next_sibling()

        self.assertEqual(len(link_btns), 1)
        self.assertEqual(link_btns[0].get_uri(), "https://shikimori.one/animes/z5114")

    @patch("anime_dlp.gui.gtk.details_page.fetch_image_cached")
    @patch("anime_dlp.gui.gtk.details_page.prefetch.get_or_fetch")
    def test_related_anime_display_and_click(self, mock_prefetch, mock_fetch_image):
        item = {"shikimori_id": "54492", "title": "Записки аптекаря"}
        window = MagicMock()
        page = DetailsPage(window=window, item=item)
        page._build_form()

        self.assertIsNotNone(page.related_box)
        self.assertFalse(page.related_box.get_visible())

        related_data = [
            {
                "name": "Монолог фармацевта 2",
                "picture": "https://shikimori.io/uploads/poster/animes/58514/test.jpeg",
                "relation": "Продолжение",
                "type": "TV Сериал",
                "url": "/animes/58514-kusuriya-no-hitorigoto-2nd-season",
            }
        ]
        page._on_related_loaded(related_data)

        self.assertTrue(page.related_box.get_visible())

        # Test clicking the related item opens DetailsPage for 58514
        page._on_related_clicked(related_data[0])
        window.push_page.assert_called_once()
        new_page = window.push_page.call_args[0][0]
        self.assertIsInstance(new_page, DetailsPage)
        self.assertEqual(new_page.item["shikimori_id"], "58514")
        self.assertEqual(new_page.item["title"], "Монолог фармацевта 2")

    @patch("anime_dlp.gui.gtk.details_page.fetch_image_cached")
    @patch("anime_dlp.gui.gtk.details_page.prefetch.get_or_fetch")
    def test_nested_details_page_push_no_duplicate_tag(self, mock_prefetch, mock_fetch_image):
        nav = Adw.NavigationView()
        window = MagicMock()
        page1 = DetailsPage(window=window, item={"shikimori_id": "54492", "title": "Anime 1"})
        page2 = DetailsPage(window=window, item={"shikimori_id": "58514", "title": "Anime 2"})
        page3 = DetailsPage(window=window, item={"shikimori_id": "54492", "title": "Anime 1 again"})

        nav.add(page1)
        nav.push(page2)
        self.assertEqual(nav.get_visible_page(), page2)
        nav.push(page3)
        self.assertEqual(nav.get_visible_page(), page3)


if __name__ == "__main__":
    unittest.main()
