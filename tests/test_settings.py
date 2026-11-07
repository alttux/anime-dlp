import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from anime_dlp.config import DOWNLOAD_DIR
from anime_dlp.core import favorites, settings as app_settings, token_manager, translations, watch_history


class TestSettingsAndBackup(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp_dir.name)
        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.patches = [
            patch("anime_dlp.core.settings.DATA_DIR", self.data_dir),
            patch("anime_dlp.core.favorites.DATA_DIR", self.data_dir),
            patch("anime_dlp.core.token_manager.DATA_DIR", self.data_dir),
            patch("anime_dlp.core.translations.DATA_DIR", self.data_dir),
            patch("anime_dlp.core.watch_history.CACHE_DIR", self.cache_dir),
        ]
        for p in self.patches:
            p.start()

        # Reset in-memory caches
        app_settings._settings_data = None
        favorites._items = None
        translations._data = None
        watch_history._data = None

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp_dir.cleanup()

    def test_default_settings(self):
        settings = app_settings.load_settings()
        self.assertEqual(settings.get("theme"), "system")
        self.assertEqual(settings.get("palette"), "system")
        self.assertEqual(settings.get("download_dir"), str(DOWNLOAD_DIR))
        self.assertTrue(settings.get("ask_download_folder"))

    def test_get_and_set_setting(self):
        app_settings.set_setting("theme", "dark")
        self.assertEqual(app_settings.get_setting("theme"), "dark")

        app_settings.set_setting("palette", "gruvbox")
        self.assertEqual(app_settings.get_setting("palette"), "gruvbox")

        app_settings.set_setting("ask_download_folder", False)
        self.assertFalse(app_settings.get_setting("ask_download_folder"))

        custom_dir = str(self.data_dir / "custom_downloads")
        app_settings.set_setting("download_dir", custom_dir)
        self.assertEqual(app_settings.get_setting("download_dir"), custom_dir)

    def test_export_all_data_structure(self):
        # Set up sample data in all subsystems
        app_settings.set_setting("theme", "light")
        app_settings.set_setting("palette", "catppuccin")

        # Favorites with different watch statuses
        item_watched = {
            "title": "Completed Anime",
            "shikimori_id": "1001",
            "series_count": 2,
        }
        item_started = {
            "title": "In Progress Anime",
            "shikimori_id": "1002",
            "series_count": 10,
        }
        item_unstarted = {
            "title": "Unstarted Anime",
            "shikimori_id": "1003",
            "series_count": 12,
        }
        favorites.add(item_watched)
        favorites.add(item_started)
        favorites.add(item_unstarted)

        watch_history.mark_watched("1001", 1, series_count=2)
        watch_history.mark_watched("1001", 2, series_count=2)
        watch_history.mark_watched("1002", 1, series_count=10)

        translations.save_selected_translation("1001", {"id": 123, "name": "Studio Band", "type": "Озвучка"})
        token_manager.save_token("test_token_12345")

        exported = app_settings.export_all_data()

        self.assertIn("version", exported)
        self.assertIn("app_version", exported)
        self.assertIn("settings", exported)
        self.assertIn("favorites", exported)
        self.assertIn("favorites_by_status", exported)
        self.assertIn("watched", exported)
        self.assertIn("translations", exported)
        self.assertEqual(exported.get("token"), "test_token_12345")

        # Check favorites_by_status breakdown
        by_status = exported["favorites_by_status"]
        self.assertIn(watch_history.STATUS_WATCHED, by_status)
        self.assertIn(watch_history.STATUS_IN_PROGRESS, by_status)
        self.assertIn(watch_history.STATUS_NOT_STARTED, by_status)

        watched_ids = [it["shikimori_id"] for it in by_status[watch_history.STATUS_WATCHED]]
        in_progress_ids = [it["shikimori_id"] for it in by_status[watch_history.STATUS_IN_PROGRESS]]
        not_started_ids = [it["shikimori_id"] for it in by_status[watch_history.STATUS_NOT_STARTED]]

        self.assertEqual(watched_ids, ["1001"])
        self.assertEqual(in_progress_ids, ["1002"])
        self.assertEqual(not_started_ids, ["1003"])

    def test_export_and_import_roundtrip(self):
        # Configure initial state
        app_settings.set_setting("theme", "dark")
        app_settings.set_setting("palette", "tokyo_night")
        app_settings.set_setting("ask_download_folder", False)
        app_settings.set_setting("download_dir", "/tmp/my_anime")

        fav = {"title": "Test Title", "shikimori_id": "9999", "series_count": 5}
        favorites.add(fav)
        watch_history.mark_watched("9999", 1, series_count=5)
        translations.save_selected_translation("9999", {"id": "77", "name": "AniLibria", "type": "Озвучка"})
        token_manager.save_token("secret_token")

        backup_file = self.data_dir / "backup.json"
        app_settings.export_all_data_to_file(backup_file)
        self.assertTrue(backup_file.exists())

        # Clear everything
        app_settings._settings_data = None
        (self.data_dir / app_settings.SETTINGS_FILE).unlink(missing_ok=True)
        favorites._items = None
        (self.data_dir / favorites.FAVORITES_FILE).unlink(missing_ok=True)
        watch_history._data = None
        (self.cache_dir / watch_history.HISTORY_FILE).unlink(missing_ok=True)
        translations._data = None
        (self.data_dir / translations.TRANSLATIONS_FILE).unlink(missing_ok=True)
        (self.data_dir / token_manager.TOKEN_FILE).unlink(missing_ok=True)

        # Verify state is cleared
        self.assertEqual(app_settings.get_setting("theme"), "system")
        self.assertEqual(favorites.load(), [])
        self.assertIsNone(token_manager.load_token())

        # Now import back
        success = app_settings.import_all_data_from_file(backup_file)
        self.assertTrue(success)

        # Verify restored state
        self.assertEqual(app_settings.get_setting("theme"), "dark")
        self.assertEqual(app_settings.get_setting("palette"), "tokyo_night")
        self.assertFalse(app_settings.get_setting("ask_download_folder"))
        self.assertEqual(app_settings.get_setting("download_dir"), "/tmp/my_anime")

        restored_favs = favorites.load()
        self.assertEqual(len(restored_favs), 1)
        self.assertEqual(restored_favs[0]["shikimori_id"], "9999")

        self.assertIn(1, watch_history.watched_episodes("9999"))
        self.assertNotIn(2, watch_history.watched_episodes("9999"))

        saved_tr = translations.get_saved_translation("9999")
        self.assertIsNotNone(saved_tr)
        self.assertEqual(saved_tr["id"], "77")

        self.assertEqual(token_manager.load_token(), "secret_token")

    def test_import_corrupted_file(self):
        bad_file = self.data_dir / "bad.json"
        bad_file.write_text("not json content", encoding="utf-8")
        self.assertFalse(app_settings.import_all_data_from_file(bad_file))


class TestThemeManagerPalettes(unittest.TestCase):
    def test_all_palettes_have_light_and_dark_definitions(self):
        from anime_dlp.gui.gtk import theme_manager

        required_palettes = ["gruvbox", "catppuccin", "monokai", "tokyo_night", "lgbtq"]
        for name in required_palettes:
            self.assertIn(name, theme_manager.PALETTES)
            self.assertIn(name, theme_manager._PALETTE_CSS)
            css_variants = theme_manager._PALETTE_CSS[name]
            self.assertIn("dark", css_variants)
            self.assertIn("light", css_variants)
            self.assertTrue(len(css_variants["dark"].strip()) > 0)
            self.assertTrue(len(css_variants["light"].strip()) > 0)
            self.assertIn("@define-color accent_color", css_variants["dark"])
            self.assertIn("@define-color accent_color", css_variants["light"])
            self.assertIn("@define-color window_bg_color", css_variants["dark"])
            self.assertIn("@define-color window_bg_color", css_variants["light"])


if __name__ == "__main__":
    unittest.main()
