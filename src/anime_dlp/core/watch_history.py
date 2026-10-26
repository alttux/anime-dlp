"""История просмотра — какие серии просмотрены и где остановился плеер.

Лежит в CACHE_DIR/watched.json, рядом с дисковым кэшем, но кнопка
«Обновить» её не трогает: cache.clear_all() удаляет только подкаталоги
images/ и meta/.

Формат — словарь по shikimori_id:
    {"<sid>": {"series_count": 12,
               "watched": [1, 2, 3],
               "positions": {"4": 312.5},
               "updated_at": <unix ts>}}

series_count запоминается вместе с отметками, чтобы сетки обложек могли
понять «просмотрено всё» без сетевого запроса за списком серий. Для фильма
series_count = 0, а просмотренная «серия» — 0.
"""

import json
import threading
import time

from anime_dlp.config import CACHE_DIR
from anime_dlp.core.cache import atomic_write

HISTORY_FILE = "watched.json"

# Досмотрел до этой доли длительности — серия считается просмотренной
# (титры в конце обычно никто не досматривает).
WATCHED_FRACTION = 0.9
# Позиции ближе к началу/концу не запоминаем — смысла продолжать с них нет.
_MIN_RESUME_SECONDS = 10

_lock = threading.Lock()
_data: dict[str, dict] | None = None


def _path():
    return CACHE_DIR / HISTORY_FILE


def _load_locked() -> dict[str, dict]:
    global _data
    if _data is None:
        try:
            raw = json.loads(_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        _data = {k: v for k, v in raw.items() if isinstance(v, dict)} if isinstance(raw, dict) else {}
    return _data


def _save_locked() -> None:
    atomic_write(_path(), json.dumps(_data, ensure_ascii=False).encode("utf-8"))


def _entry_locked(shikimori_id: str) -> dict:
    entry = _load_locked().setdefault(shikimori_id, {})
    entry.setdefault("watched", [])
    entry.setdefault("positions", {})
    return entry


def watched_episodes(shikimori_id: str | None) -> set[int]:
    if not shikimori_id:
        return set()
    with _lock:
        entry = _load_locked().get(shikimori_id) or {}
        return {int(e) for e in entry.get("watched", [])}


def is_fully_watched(shikimori_id: str | None) -> bool:
    """Все серии просмотрены — галочка на обложке. Для фильма достаточно
    просмотренной «серии» 0."""
    if not shikimori_id:
        return False
    with _lock:
        entry = _load_locked().get(shikimori_id)
        if not entry or "series_count" not in entry:
            return False
        watched = {int(e) for e in entry.get("watched", [])}
        count = entry["series_count"] or 0
    if count <= 0:
        return 0 in watched
    return all(n in watched for n in range(1, count + 1))


def set_series_count(shikimori_id: str, series_count: int | None) -> None:
    """Запоминает число серий (страница аниме знает его после get_info)."""
    if not shikimori_id:
        return
    with _lock:
        entry = _load_locked().get(shikimori_id)
        # Без отметок записи не заводим: не засоряем файл каждым открытым
        # аниме. mark_watched() сам передаст число серий.
        if entry is None or entry.get("series_count") == (series_count or 0):
            return
        entry["series_count"] = series_count or 0
        _save_locked()


def mark_watched(
    shikimori_id: str, episode: int, series_count: int | None, watched: bool = True
) -> None:
    with _lock:
        entry = _entry_locked(shikimori_id)
        episodes = {int(e) for e in entry["watched"]}
        if watched:
            episodes.add(episode)
            entry["positions"].pop(str(episode), None)
        else:
            episodes.discard(episode)
        entry["watched"] = sorted(episodes)
        entry["series_count"] = series_count or 0
        entry["updated_at"] = time.time()
        _save_locked()


def get_position(shikimori_id: str, episode: int) -> float:
    with _lock:
        entry = _load_locked().get(shikimori_id) or {}
        return float(entry.get("positions", {}).get(str(episode), 0.0))


def save_position(
    shikimori_id: str, episode: int, position: float, duration: float, series_count: int | None
) -> None:
    """Запоминает позицию для продолжения просмотра. Если досмотрено до
    WATCHED_FRACTION — вместо позиции ставит отметку «просмотрено»."""
    if duration > 0 and position >= duration * WATCHED_FRACTION:
        if episode not in watched_episodes(shikimori_id):
            mark_watched(shikimori_id, episode, series_count)
        return
    with _lock:
        entry = _entry_locked(shikimori_id)
        if position < _MIN_RESUME_SECONDS:
            if entry["positions"].pop(str(episode), None) is None:
                return
        else:
            entry["positions"][str(episode)] = round(position, 1)
        entry["series_count"] = series_count or 0
        entry["updated_at"] = time.time()
        _save_locked()
