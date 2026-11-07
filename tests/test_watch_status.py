import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dlp.core import watch_history


class WatchStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.patcher = patch(
            "anime_dlp.core.watch_history._path",
            return_value=Path(self.temp_dir.name) / "watched.json",
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        watch_history._data = None

    def test_status_not_started(self):
        item = {"shikimori_id": "123", "episodes_count": 12}
        status = watch_history.get_watch_status(item)
        self.assertEqual(status, watch_history.STATUS_NOT_STARTED)

    def test_status_in_progress_from_watched_episode(self):
        item = {"shikimori_id": "123", "episodes_count": 12}
        watch_history.mark_watched("123", episode=1, series_count=12)

        status = watch_history.get_watch_status(item)
        self.assertEqual(status, watch_history.STATUS_IN_PROGRESS)

    def test_status_in_progress_from_saved_position(self):
        item = {"shikimori_id": "123", "episodes_count": 12}
        watch_history.save_position("123", episode=1, position=120.0, duration=1400.0, series_count=12)

        status = watch_history.get_watch_status(item)
        self.assertEqual(status, watch_history.STATUS_IN_PROGRESS)

    def test_status_watched_all_episodes(self):
        item = {"shikimori_id": "123", "episodes_count": 3}
        for ep in (1, 2, 3):
            watch_history.mark_watched("123", episode=ep, series_count=3)

        status = watch_history.get_watch_status(item)
        self.assertEqual(status, watch_history.STATUS_WATCHED)

    def test_status_watched_movie(self):
        item = {"shikimori_id": "movie_1", "type": "anime", "episodes_count": 0}
        watch_history.mark_watched("movie_1", episode=0, series_count=0)

        status = watch_history.get_watch_status(item)
        self.assertEqual(status, watch_history.STATUS_WATCHED)


if __name__ == "__main__":
    unittest.main()
