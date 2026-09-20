import unittest
from unittest.mock import patch

from anime_dlp.core.playback import (
    PlaybackSources,
    _available_qualities,
    _normalise_base_url,
    get_playback_sources,
)


class PlaybackSourcesTests(unittest.TestCase):
    def test_hls_url_uses_selected_quality(self):
        sources = PlaybackSources(
            episode=3,
            translation_id="610",
            base_url="https://cdn.example/video/",
            qualities=(360, 480, 720),
            skip_segments=(),
        )

        self.assertEqual(
            sources.hls_url(480),
            "https://cdn.example/video/480.mp4:hls:manifest.m3u8",
        )
        self.assertEqual(sources.default_quality, 720)

    def test_hls_url_rejects_unavailable_quality(self):
        sources = PlaybackSources(1, "1", "https://cdn.example/", (360,), ())

        with self.assertRaises(ValueError):
            sources.hls_url(720)

    def test_normalise_protocol_relative_url(self):
        self.assertEqual(
            _normalise_base_url("//cdn.example/path"),
            "https://cdn.example/path/",
        )

    def test_normalise_rejects_invalid_url(self):
        with self.assertRaises(ValueError):
            _normalise_base_url("not-a-url")

    def test_available_qualities_follow_kodik_ladder(self):
        self.assertEqual(_available_qualities(720), (360, 480, 720))
        self.assertEqual(_available_qualities(480), (360, 480))
        self.assertEqual(_available_qualities(1080), (360, 480, 720, 1080))

    def test_nonstandard_maximum_is_retained(self):
        self.assertEqual(_available_qualities(540), (360, 480, 540))

    @patch("anime_dlp.core.playback.get_download_link")
    def test_get_playback_sources_resolves_episode_once(self, get_link):
        get_link.return_value = (
            "//cdn.example/path/",
            720,
            [[0, 90], [1200, 1300]],
        )

        sources = get_playback_sources("42", 7, "610")

        get_link.assert_called_once_with("42", 7, "610")
        self.assertEqual(sources.episode, 7)
        self.assertEqual(sources.translation_id, "610")
        self.assertEqual(sources.qualities, (360, 480, 720))
        self.assertEqual(sources.skip_segments, ((0, 90), (1200, 1300)))


if __name__ == "__main__":
    unittest.main()
