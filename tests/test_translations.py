import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dlp.core import translations


class TranslationsStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.patcher = patch(
            "anime_dlp.core.translations._path",
            return_value=Path(self.temp_dir.name) / "translations.json",
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        translations._data = None

    def test_save_and_retrieve_anime_translation(self):
        t1 = {"id": 610, "name": "AniLibria.TV (12 эп.)", "type": "Озвучка"}
        translations.save_selected_translation("54492", t1)

        saved = translations.get_saved_translation("54492")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["id"], "610")
        self.assertEqual(saved["name"], "AniLibria.TV (12 эп.)")

        last = translations.get_last_used_translation()
        self.assertIsNotNone(last)
        self.assertEqual(last["id"], "610")

    def test_find_matching_translation_index_by_id(self):
        t1 = {"id": "609", "name": "AniDUB (12 эп.)"}
        t2 = {"id": "610", "name": "AniLibria.TV (12 эп.)"}
        translations.save_selected_translation("54492", t2)

        available = [t1, t2]
        idx = translations.find_matching_translation_index(available, "54492")
        self.assertEqual(idx, 1)

    def test_find_matching_translation_index_by_name(self):
        # Если ID отличается (например, другой релиз), но название команды совпадает
        translations.save_selected_translation(
            "54492", {"id": "999", "name": "AniLibria.TV (12 эп.)"}
        )
        available = [
            {"id": "609", "name": "AniDUB (24 эп.)"},
            {"id": "610", "name": "AniLibria.TV (24 эп.)"},
        ]
        idx = translations.find_matching_translation_index(available, "54492")
        self.assertEqual(idx, 1)

    def test_fallback_to_last_used_translation_for_new_anime(self):
        # Пользователь выбрал озвучку на одном аниме
        translations.save_selected_translation(
            "11111", {"id": "610", "name": "AniLibria.TV (12 эп.)"}
        )

        # Открываем совершенно другое аниме, для которого ещё не выбирали озвучку
        available_other = [
            {"id": "609", "name": "AniDUB (10 эп.)"},
            {"id": "777", "name": "AniLibria.TV (10 эп.)"},
        ]
        idx = translations.find_matching_translation_index(available_other, "22222")
        self.assertEqual(idx, 1)


if __name__ == "__main__":
    unittest.main()
