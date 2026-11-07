from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from anime_dlp.config import DOWNLOAD_DIR
from anime_dlp.core import settings as app_settings
from anime_dlp.gui.gtk.details_page import DetailsPage
from anime_dlp.gui.gtk.home_page import HomePage
from anime_dlp.gui.gtk.settings_dialog import SettingsDialog, THEME_KEYS, PALETTE_KEYS


class GtkSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure GTK/Adw is initialized
        if not Adw.is_initialized():
            Adw.init()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.patches = [
            patch("anime_dlp.core.settings.DATA_DIR", self.data_dir),
            patch("anime_dlp.core.translations.DATA_DIR", self.data_dir),
            patch("anime_dlp.core.favorites.DATA_DIR", self.data_dir),
            patch("anime_dlp.core.watch_history.CACHE_DIR", self.cache_dir),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(self._stop_patches)
        self.addCleanup(self.temp_dir.cleanup)

        app_settings._settings_data = None
        self.window = MagicMock()
        self.window.download_dir = DOWNLOAD_DIR

    def _stop_patches(self):
        for p in reversed(self.patches):
            p.stop()

    def test_settings_dialog_initial_state(self):
        app_settings.set_setting("theme", "dark")
        app_settings.set_setting("palette", "monokai")
        app_settings.set_setting("ask_download_folder", False)

        dlg = SettingsDialog(self.window)
        self.assertEqual(dlg.theme_combo.get_selected(), THEME_KEYS.index("dark"))
        self.assertEqual(dlg.palette_combo.get_selected(), PALETTE_KEYS.index("monokai"))
        self.assertFalse(dlg.ask_folder_switch.get_active())

    def test_theme_and_palette_change_signals(self):
        dlg = SettingsDialog(self.window)

        # Change theme to light
        dlg.theme_combo.set_selected(THEME_KEYS.index("light"))
        self.assertEqual(app_settings.get_setting("theme"), "light")

        # Change palette to gruvbox
        dlg.palette_combo.set_selected(PALETTE_KEYS.index("gruvbox"))
        self.assertEqual(app_settings.get_setting("palette"), "gruvbox")

        # Toggle ask folder
        dlg.ask_folder_switch.set_active(False)
        self.assertFalse(app_settings.get_setting("ask_download_folder"))

    def test_reset_folder_button(self):
        app_settings.set_setting("download_dir", "/custom/path")
        dlg = SettingsDialog(self.window)
        dlg._on_reset_folder_clicked(None)

        self.assertEqual(app_settings.get_setting("download_dir"), str(DOWNLOAD_DIR))
        self.assertEqual(self.window.download_dir, DOWNLOAD_DIR)

    def test_details_page_bypasses_file_dialog_when_ask_folder_is_false(self):
        app_settings.set_setting("ask_download_folder", False)
        custom_dir = Path("/custom/download/target")
        self.window.download_dir = custom_dir

        item = {"shikimori_id": "test_sid", "title": "Test Title"}
        page = DetailsPage(window=self.window, item=item)
        page._on_info_loaded(
            {
                "series_count": 1,
                "translations": [
                    {"id": "111", "type": "Озвучка", "name": "Studio Band", "series_range": [1, 1]},
                ],
            },
            None,
        )
        page.episode_checks[1].set_active(True)

        with patch("gi.repository.Gtk.FileDialog") as mock_file_dialog:
            page._on_download_clicked(None)
            # FileDialog should NOT have been instantiated
            mock_file_dialog.assert_not_called()
            # push_page should have been called with DownloadPage
            self.window.push_page.assert_called_once()
            download_page_arg = self.window.push_page.call_args[0][0]
            self.assertEqual(download_page_arg.download_dir, custom_dir)
            self.assertEqual(download_page_arg.eps_to_download, [1])

    @patch("anime_dlp.gui.gtk.home_page.show_settings_dialog")
    def test_home_page_settings_button(self, mock_show_settings):
        page = HomePage(window=self.window)
        page._on_settings_clicked(None)
        mock_show_settings.assert_called_once_with(self.window)


if __name__ == "__main__":
    unittest.main()
