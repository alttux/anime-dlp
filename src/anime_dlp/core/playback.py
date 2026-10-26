"""Источник серий для онлайн-плеера (общий, без привязки к GUI-тулкиту).

Отвечает на вопросы «какой m3u8 играть для серии N в качестве Q» и «какая
серия следующая/предыдущая» для выбранной озвучки. Всё, что касается сети,
— блокирующие вызовы: GUI зовёт их из фонового потока.

Kodik не отдаёт master-плейлист со всеми качествами: на каждое качество
свой `<q>.mp4:hls:manifest.m3u8` рядом с mp4. Поэтому смена качества —
это загрузка другого плейлиста той же серии с переходом на ту же позицию.
"""

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from anime_dlp.core.anime_service import get_download_link

QUALITIES = (360, 480, 720)
DEFAULT_QUALITY = 720

# Ссылки Kodik подписаны и со временем протухают; в пределах одного
# сеанса просмотра держим их недолго, а при ошибке воспроизведения
# сбрасываем (invalidate) и запрашиваем заново.
_LINK_TTL_SECONDS = 30 * 60


@dataclass(frozen=True)
class EpisodeSource:
    episode: int
    link: str  # //host/path/ — без схемы и качества, как отдаёт get_link
    max_quality: int
    skip_segments: tuple[tuple[int, int], ...]  # опенинг/эндинг, секунды

    @property
    def qualities(self) -> list[int]:
        available = [q for q in QUALITIES if q <= self.max_quality]
        return available or [self.max_quality]

    def pick_quality(self, preferred: int) -> int:
        """Ближайшее доступное качество не выше желаемого (иначе минимальное)."""
        candidates = [q for q in self.qualities if q <= preferred]
        return max(candidates) if candidates else min(self.qualities)

    def playlist_url(self, quality: int) -> str:
        return f"https:{self.link}{quality}.mp4:hls:manifest.m3u8"


def episode_range(series_count: int | None, translation: dict) -> list[int]:
    """Серии, доступные в выбранной озвучке. Фильм — [0]."""
    if not series_count:
        return [0]
    first, last = translation.get("series_range") or (1, series_count)
    first = max(1, int(first))
    last = min(int(last), series_count)
    return list(range(first, last + 1)) or [0]


class PlaybackSource:
    """Ссылки на серии одной озвучки одного аниме, с кэшем и предзагрузкой.

    Ключ кэша — номер серии; каждый ответ get_download_link кладётся строго
    под тот номер, для которого его запрашивали, поэтому гонки «нажал
    «следующая» дважды» не могут подменить одну серию другой."""

    def __init__(self, shikimori_id: str, translation_id: str, episodes: list[int]):
        self.shikimori_id = shikimori_id
        self.translation_id = translation_id
        self.episodes = episodes
        self._lock = threading.Lock()
        self._cache: dict[int, tuple[float, EpisodeSource]] = {}
        self._pending: dict[int, Future] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="play-link")

    # --- навигация -------------------------------------------------------

    def previous_episode(self, episode: int) -> int | None:
        index = self.episodes.index(episode) if episode in self.episodes else -1
        return self.episodes[index - 1] if index > 0 else None

    def next_episode(self, episode: int) -> int | None:
        if episode not in self.episodes:
            return None
        index = self.episodes.index(episode)
        return self.episodes[index + 1] if index + 1 < len(self.episodes) else None

    # --- ссылки ----------------------------------------------------------

    def _fetch(self, episode: int) -> EpisodeSource:
        link, max_quality, skip = get_download_link(
            self.shikimori_id, episode, self.translation_id
        )
        source = EpisodeSource(
            episode=episode,
            link=link,
            max_quality=int(max_quality),
            skip_segments=tuple((int(a), int(b)) for a, b in (skip or []) if b > a),
        )
        with self._lock:
            self._cache[episode] = (time.monotonic(), source)
            self._pending.pop(episode, None)
        return source

    def _cached(self, episode: int) -> EpisodeSource | None:
        entry = self._cache.get(episode)
        if entry and time.monotonic() - entry[0] < _LINK_TTL_SECONDS:
            return entry[1]
        return None

    def resolve(self, episode: int) -> EpisodeSource:
        """Блокирующий вызов: ссылка из кэша, из уже идущей предзагрузки
        или новым запросом."""
        with self._lock:
            cached = self._cached(episode)
            future = self._pending.get(episode)
        if cached is not None:
            return cached
        if future is not None:
            try:
                return future.result()
            except Exception:
                pass  # предзагрузка упала — попробуем ещё раз ниже
        return self._fetch(episode)

    def prefetch(self, episode: int | None) -> None:
        if episode is None:
            return
        with self._lock:
            if self._cached(episode) is not None or episode in self._pending:
                return
            future = self._executor.submit(self._fetch, episode)
            self._pending[episode] = future
        # Ошибку предзагрузки не теряем молча, но и не роняем поток:
        # resolve() повторит запрос сам.
        future.add_done_callback(lambda f: f.exception())

    def invalidate(self, episode: int) -> None:
        with self._lock:
            self._cache.pop(episode, None)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
