import unittest
from unittest.mock import MagicMock, patch

from anime_dlp.core.playback import (
    EpisodeSource,
    PlaybackSource,
    episode_range,
)


class EpisodeSourceTests(unittest.TestCase):
    def test_direct_and_hls_urls(self):
        source = EpisodeSource(
            episode=1,
            link="//cdn.example.com/path/",
            max_quality=720,
            skip_segments=((0, 90),),
            supports_mp4=True,
        )
        self.assertEqual(source.direct_url(720), "https://cdn.example.com/path/720.mp4")
        self.assertEqual(
            source.hls_url(720),
            "https://cdn.example.com/path/720.mp4:hls:manifest.m3u8",
        )
        self.assertEqual(source.stream_url(720), "https://cdn.example.com/path/720.mp4")
        self.assertEqual(source.playlist_url(720), "https://cdn.example.com/path/720.mp4")

    def test_fallback_to_hls_when_mp4_unsupported(self):
        source = EpisodeSource(
            episode=1,
            link="//cdn.example.com/path/",
            max_quality=720,
            skip_segments=(),
            supports_mp4=False,
        )
        self.assertEqual(
            source.stream_url(720),
            "https://cdn.example.com/path/720.mp4:hls:manifest.m3u8",
        )
        self.assertEqual(
            source.playlist_url(720),
            "https://cdn.example.com/path/720.mp4:hls:manifest.m3u8",
        )

    def test_available_qualities(self):
        source720 = EpisodeSource(1, "//link/", 720, ())
        self.assertEqual(source720.qualities, [360, 480, 720])

        source480 = EpisodeSource(1, "//link/", 480, ())
        self.assertEqual(source480.qualities, [360, 480])

        source360 = EpisodeSource(1, "//link/", 360, ())
        self.assertEqual(source360.qualities, [360])

    def test_pick_quality(self):
        source = EpisodeSource(1, "//link/", 720, ())
        self.assertEqual(source.pick_quality(720), 720)
        self.assertEqual(source.pick_quality(1080), 720)
        self.assertEqual(source.pick_quality(480), 480)
        self.assertEqual(source.pick_quality(360), 360)


class PlaybackSourceTests(unittest.TestCase):
    def test_navigation(self):
        source = PlaybackSource("123", "456", [1, 2, 3])
        self.assertIsNone(source.previous_episode(1))
        self.assertEqual(source.next_episode(1), 2)
        self.assertEqual(source.previous_episode(2), 1)
        self.assertEqual(source.next_episode(2), 3)
        self.assertIsNone(source.next_episode(3))

    def test_episode_range(self):
        self.assertEqual(episode_range(None, {}), [0])
        self.assertEqual(episode_range(12, {"series_range": (1, 12)}), list(range(1, 13)))
        self.assertEqual(episode_range(12, {"series_range": (5, 8)}), [5, 6, 7, 8])

    @patch("anime_dlp.core.playback.get_session")
    @patch("anime_dlp.core.playback.get_download_link")
    def test_resolve_probes_mp4_success(self, mock_get_link, mock_get_session):
        mock_get_link.return_value = ("//cdn.example.com/video/", 720, [(10, 20)])
        mock_response = MagicMock()
        mock_response.status_code = 206
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        source = PlaybackSource("sid", "tid", [1])
        res = source.resolve(1)
        self.assertTrue(res.supports_mp4)
        self.assertEqual(res.stream_url(720), "https://cdn.example.com/video/720.mp4")
        source.close()

    @patch("anime_dlp.core.playback.get_session")
    @patch("anime_dlp.core.playback.get_download_link")
    def test_resolve_probes_mp4_failure_falls_back_to_hls(self, mock_get_link, mock_get_session):
        mock_get_link.return_value = ("//cdn.example.com/video/", 720, [])
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        source = PlaybackSource("sid", "tid", [1])
        res = source.resolve(1)
        self.assertFalse(res.supports_mp4)
        self.assertEqual(
            res.stream_url(720),
            "https://cdn.example.com/video/720.mp4:hls:manifest.m3u8",
        )
        source.close()


if __name__ == "__main__":
    unittest.main()
