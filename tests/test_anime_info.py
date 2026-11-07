import unittest

from anime_dlp.core.anime_info import (
    AnimeInfo,
    _derive_year,
    build_detail_rows,
    extract_anime_info,
    has_any_info,
)


class AnimeInfoTests(unittest.TestCase):
    def test_derive_year_prioritizes_item_year(self):
        # В тайтлах с несколькими сезонами material_data['year'] берётся с Кинопоиска
        # (год первого сезона, например 2023), а в item['year'] лежит год конкретного сезона (2026).
        item = {"year": 2026}
        material = {"year": 2023, "aired_at": "2026-10-02"}
        self.assertEqual(_derive_year(item, material), 2026)

    def test_derive_year_falls_back_to_aired_at(self):
        # Если item['year'] отсутствует, год должен извлекаться из даты премьеры сезона (aired_at).
        item = {}
        material = {"year": 2023, "aired_at": "2026-10-02"}
        self.assertEqual(_derive_year(item, material), 2026)

    def test_derive_year_falls_back_to_material_year(self):
        # Если ни item['year'], ни aired_at нет, берется material['year'].
        item = {}
        material = {"year": 2023}
        self.assertEqual(_derive_year(item, material), 2023)

    def test_derive_year_none_when_no_data(self):
        self.assertIsNone(_derive_year({}, {}))

    def test_extract_anime_info_multi_season_example(self):
        # Данные из примера «Записки аптекаря [ТВ-3, часть 1]»
        item = {
            "title": "Записки аптекаря [ТВ-3, часть 1]",
            "title_orig": "Kusuriya no Hitorigoto (2026)",
            "type": "anime-serial",
            "year": 2026,
            "shikimori_id": "61987",
            "kinopoisk_id": "5258557",
            "material_data": {
                "title": "Монолог фармацевта",
                "anime_title": "Монолог фармацевта 3",
                "anime_kind": "tv",
                "anime_status": "ongoing",
                "year": 2023,
                "aired_at": "2026-10-02",
                "description": "Описание с Кинопоиска первого сезона",
                "anime_description": "Описание 3-го сезона с Shikimori",
                "shikimori_rating": 8.62,
                "shikimori_votes": 1079,
                "episodes_total": 12,
                "episodes_aired": 6,
                "anime_poster_url": "https://example.com/poster3.jpg",
                "poster_url": "https://example.com/poster_kp.jpg",
                "anime_genres": ["Драма", "Исторический"],
                "anime_studios": ["OLM"],
            },
        }

        info = extract_anime_info(item)
        self.assertEqual(info.year, 2026)
        self.assertEqual(info.season, "Осень")
        self.assertEqual(info.kind, "Сериал")
        self.assertEqual(info.status, "Онгоинг")
        self.assertEqual(info.description, "Описание 3-го сезона с Shikimori")
        self.assertEqual(info.poster_url, "https://example.com/poster3.jpg")
        self.assertEqual(info.episodes_total, 12)
        self.assertEqual(info.episodes_aired, 6)

        rows = dict(build_detail_rows(info))
        self.assertEqual(rows.get("Год"), "2026")
        self.assertEqual(rows.get("Сезон"), "Осень")
        self.assertEqual(rows.get("Статус"), "Онгоинг")

    def test_has_any_info_with_only_year(self):
        info = AnimeInfo(
            description=None,
            genres=[],
            studios=[],
            status=None,
            score=None,
            votes=None,
            episodes_total=None,
            episodes_aired=None,
            poster_url=None,
            kind=None,
            year=2026,
            season=None,
            age_rating=None,
            title_orig=None,
            duration=None,
        )
        self.assertTrue(has_any_info(info))


if __name__ == "__main__":
    unittest.main()
