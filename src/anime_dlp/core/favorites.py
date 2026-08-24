"""Избранное — аниме, отмеченные звёздочкой на странице аниме.

Хранится одним JSON-массивом полных записей Kodik (тех же словарей, что
ходят между экранами GUI: title, shikimori_id, material_data и т.д.) в
DATA_DIR — рядом с токеном, а не в CACHE_DIR, чтобы кнопка «Обновить»
(очистка кэша) не стирала пользовательские отметки.

Полная запись, а не один shikimori_id, нужна затем, чтобы вкладка
«Избранное» рисовала обложки и открывала страницу аниме без единого
сетевого запроса.
"""

import json
import threading

from anime_dlp.config import DATA_DIR, FAVORITES_FILE
from anime_dlp.core.cache import atomic_write

_lock = threading.Lock()
_items: list[dict] | None = None  # ленивый кэш содержимого файла


def _path():
    return DATA_DIR / FAVORITES_FILE


def _load_locked() -> list[dict]:
    global _items
    if _items is None:
        try:
            raw = _path().read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            data = []
        _items = [i for i in data if isinstance(i, dict)] if isinstance(data, list) else []
    return _items


def _save_locked() -> None:
    payload = json.dumps(_items, ensure_ascii=False)
    atomic_write(_path(), payload.encode("utf-8"))


def load() -> list[dict]:
    """Список избранного, недавно добавленные — первыми."""
    with _lock:
        return list(_load_locked())


def is_favorite(shikimori_id: str | None) -> bool:
    if not shikimori_id:
        return False
    with _lock:
        return any(i.get("shikimori_id") == shikimori_id for i in _load_locked())


def add(item: dict) -> None:
    shikimori_id = item.get("shikimori_id")
    if not shikimori_id:
        return
    with _lock:
        items = _load_locked()
        if any(i.get("shikimori_id") == shikimori_id for i in items):
            return
        items.insert(0, item)
        _save_locked()


def remove(shikimori_id: str) -> None:
    global _items
    if not shikimori_id:
        return
    with _lock:
        items = _load_locked()
        remaining = [i for i in items if i.get("shikimori_id") != shikimori_id]
        if len(remaining) == len(items):
            return
        _items = remaining
        _save_locked()


def toggle(item: dict) -> bool:
    """Переключает отметку и возвращает новое состояние (True — в избранном)."""
    shikimori_id = item.get("shikimori_id")
    if not shikimori_id:
        return False
    if is_favorite(shikimori_id):
        remove(shikimori_id)
        return False
    add(item)
    return True
