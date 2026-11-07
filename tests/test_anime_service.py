import unittest
from unittest.mock import MagicMock, patch

from anime_dlp.core.anime_service import _dedupe_by_anime, search_anime


class AnimeServiceTests(unittest.TestCase):
    def test_dedupe_keeps_distinct_seasons_with_shikimori(self):
        items = [
            {"title": "Записки аптекаря [ТВ-1]", "shikimori_id": "54492", "link": "//link1"},
            {"title": "Записки аптекаря [ТВ-1]", "shikimori_id": "54492", "link": "//link2"},
            {"title": "Записки аптекаря [ТВ-2]", "shikimori_id": "58514", "link": "//link3"},
            {"title": "Записки аптекаря [ТВ-3, часть 1]", "shikimori_id": "61987", "link": "//link4"},
        ]
        deduped = _dedupe_by_anime(items)
        self.assertEqual(len(deduped), 3)
        self.assertEqual(
            [d["shikimori_id"] for d in deduped],
            ["54492", "58514", "61987"],
        )

    def test_dedupe_keeps_distinct_seasons_without_shikimori_sharing_kinopoisk_id(self):
        # Если shikimori_id нет, но есть общий kinopoisk_id, разные сезоны не должны склеиваться
        items = [
            {"title": "Шоу [ТВ-1]", "kinopoisk_id": "123", "link": "//link1"},
            {"title": "Шоу [ТВ-1]", "kinopoisk_id": "123", "link": "//link2"},
            {"title": "Шоу [ТВ-2]", "kinopoisk_id": "123", "link": "//link3"},
        ]
        deduped = _dedupe_by_anime(items)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(
            [d["title"] for d in deduped],
            ["Шоу [ТВ-1]", "Шоу [ТВ-2]"],
        )

    @patch("anime_dlp.core.anime_service.cache.get_cached_json")
    @patch("anime_dlp.core.anime_service.cache.store_json")
    @patch("anime_dlp.core.anime_service._get_parser")
    def test_search_anime_passes_popular_page_limit(
        self, mock_get_parser, mock_store_json, mock_get_cache
    ):
        mock_get_cache.return_value = None
        mock_parser = MagicMock()
        mock_parser.search.return_value = [
            {"title": "Записки аптекаря [ТВ-3, часть 1]", "shikimori_id": "61987", "link": "//l1"}
        ]
        mock_get_parser.return_value = mock_parser

        results = search_anime("Записки аптекаря")
        self.assertEqual(len(results), 1)
        mock_parser.search.assert_called_once_with(
            title="Записки аптекаря",
            limit=100,
            include_material_data=True,
            only_anime=True,
            strict=False,
        )

    @patch("anime_dlp.core.anime_service.cache.get_cached_json")
    @patch("anime_dlp.core.anime_service.cache.store_json")
    @patch("anime_dlp.core.anime_service._get_parser")
    def test_get_anime_by_shikimori_id(self, mock_get_parser, mock_store_json, mock_get_cache):
        from anime_dlp.core.anime_service import get_anime_by_shikimori_id

        mock_get_cache.return_value = None
        mock_parser = MagicMock()
        mock_parser.search_by_id.return_value = [
            {"title": "Fullmetal Alchemist", "shikimori_id": "5114"}
        ]
        mock_get_parser.return_value = mock_parser

        item = get_anime_by_shikimori_id("5114")
        self.assertIsNotNone(item)
        self.assertEqual(item["title"], "Fullmetal Alchemist")
        mock_parser.search_by_id.assert_called_once_with("5114", "shikimori")
        mock_store_json.assert_called_once_with("item:shikimori:5114", item)

    @patch("anime_dlp.core.anime_service.cache.get_cached_json")
    @patch("anime_dlp.core.anime_service.cache.store_json")
    @patch("anime_parsers_ru.ShikimoriParser")
    def test_get_shikimori_additional_info(self, mock_shiki_parser_cls, mock_store_json, mock_get_cache):
        from anime_dlp.core.anime_service import get_shikimori_additional_info

        mock_get_cache.return_value = None
        mock_instance = MagicMock()
        mock_instance.additional_anime_info.return_value = {
            "related": [{"name": "Season 2", "url": "/animes/58514"}]
        }
        mock_shiki_parser_cls.return_value = mock_instance

        res = get_shikimori_additional_info("54492")
        self.assertIn("related", res)
        self.assertEqual(len(res["related"]), 1)
        mock_instance.additional_anime_info.assert_called_once_with("https://shikimori.io/animes/z54492")
        mock_store_json.assert_called_once_with("shiki_add:54492", res)


if __name__ == "__main__":
    unittest.main()
