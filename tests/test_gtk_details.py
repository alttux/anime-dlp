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


if __name__ == "__main__":
    unittest.main()
