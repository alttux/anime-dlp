"""Фоновая предзагрузка доп. информации об аниме (озвучки/серии), общая для
GTK и Qt бэкендов. Как только тайтл появляется в сетке каталога или в
результатах поиска, запускается фоновый запрос get_anime_info — к моменту,
когда пользователь откроет DetailsPage, результат обычно уже готов."""

import threading
from concurrent.futures import Future, ThreadPoolExecutor

from anime_dlp.core.anime_service import get_anime_info

_MAX_WORKERS = 3  # ограничиваем параллелизм запросов к Kodik
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="info-prefetch")
_lock = threading.Lock()
_cache: dict[str, dict] = {}
_futures: dict[str, Future] = {}


def prefetch(shikimori_id: str | None) -> None:
    """Запускает фоновую загрузку доп. инфы, если она ещё не запущена и не
    закэширована. Безопасно вызывать многократно для одного и того же id."""
    if not shikimori_id:
        return
    with _lock:
        if shikimori_id in _cache or shikimori_id in _futures:
            return
        _futures[shikimori_id] = _executor.submit(_do_fetch, shikimori_id)


def _do_fetch(shikimori_id: str) -> dict:
    info = get_anime_info(shikimori_id)
    with _lock:
        _cache[shikimori_id] = info
        _futures.pop(shikimori_id, None)
    return info


def get_or_fetch(shikimori_id: str) -> dict:
    """Блокирующий вызов — безопасен из фонового потока/QThread. Отдаёт
    готовый кэш, дожидается уже запущенной предзагрузки или запускает новую."""
    with _lock:
        cached = _cache.get(shikimori_id)
        future = _futures.get(shikimori_id)
    if cached is not None:
        return cached
    if future is not None:
        return future.result()
    return _do_fetch(shikimori_id)
