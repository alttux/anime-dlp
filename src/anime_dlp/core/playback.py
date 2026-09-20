from dataclasses import dataclass
from urllib.parse import urlsplit

from anime_dlp.core.anime_service import get_download_link


_STANDARD_QUALITIES = (360, 480, 720, 1080)


@dataclass(frozen=True)
class PlaybackSources:
    """All stream variants needed to play one Kodik episode."""

    episode: int
    translation_id: str
    base_url: str
    qualities: tuple[int, ...]
    skip_segments: tuple[tuple[int, int], ...]

    @property
    def default_quality(self) -> int:
        return self.qualities[-1]

    def hls_url(self, quality: int) -> str:
        if quality not in self.qualities:
            raise ValueError(f"Quality {quality}p is not available")
        return f"{self.base_url}{quality}.mp4:hls:manifest.m3u8"


def _normalise_base_url(base_url: str) -> str:
    if base_url.startswith("//"):
        base_url = f"https:{base_url}"
    elif not base_url.startswith(("http://", "https://")):
        raise ValueError("Kodik returned an invalid video URL")

    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Kodik returned an invalid video URL")
    if not base_url.endswith("/"):
        base_url = f"{base_url}/"
    return base_url


def _available_qualities(max_quality: int) -> tuple[int, ...]:
    if max_quality <= 0:
        raise ValueError("Kodik returned an invalid maximum quality")

    qualities = tuple(q for q in _STANDARD_QUALITIES if q <= max_quality)
    if max_quality not in qualities:
        qualities = (*qualities, max_quality)
    return qualities


def get_playback_sources(
    shikimori_id: str,
    episode: int,
    translation_id: str,
) -> PlaybackSources:
    """Resolve one episode once and expose its HLS quality variants.

    Kodik's parser returns a common URL prefix and the highest available
    quality. Keeping that response in one object lets the player switch
    quality without repeating the expensive iframe/API lookup.
    """
    base_url, max_quality, skip_segments = get_download_link(
        shikimori_id,
        episode,
        translation_id,
    )
    return PlaybackSources(
        episode=episode,
        translation_id=str(translation_id),
        base_url=_normalise_base_url(base_url),
        qualities=_available_qualities(int(max_quality)),
        skip_segments=tuple(tuple(segment) for segment in skip_segments),
    )
