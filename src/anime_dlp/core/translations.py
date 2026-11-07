"""Хранилище выбранных вариантов озвучки.

Запоминает выбранную пользователем озвучку для каждого аниме (по shikimori_id),
а также последнюю выбранную озвучку вообще (чтобы автоматически подставлять её
для новых тайтлов, если там доступна та же студия/автор).

Хранится в DATA_DIR/translations.json рядом с favorites.json.
Формат:
{
    "by_anime": {
        "<shikimori_id>": {
            "id": "<translation_id>",
            "name": "AniLibria.TV (12 эп.)",
            "type": "Озвучка"
        }
    },
    "last_used": {
        "id": "<translation_id>",
        "name": "AniLibria.TV (12 эп.)",
        "type": "Озвучка"
    }
}
"""

import json
import re
import threading

from anime_dlp.config import DATA_DIR, TRANSLATIONS_FILE
from anime_dlp.core.cache import atomic_write

_lock = threading.Lock()
_data: dict | None = None


def _path():
    return DATA_DIR / TRANSLATIONS_FILE


def _load_locked() -> dict:
    global _data
    if _data is None:
        try:
            raw = json.loads(_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        _data = raw if isinstance(raw, dict) else {}
        _data.setdefault("by_anime", {})
    return _data


def _save_locked() -> None:
    atomic_write(_path(), json.dumps(_data, ensure_ascii=False).encode("utf-8"))


def _normalize_name(name: str) -> str:
    """Удаляет из названия озвучки число эпизодов, скобки и нормализует регистр:
    'AniLibria.TV (12 эп.)' -> 'anilibria.tv'
    """
    clean = re.sub(r"\s*\(\d+\s*эп\.?\)", "", name, flags=re.IGNORECASE)
    return clean.strip().lower()


def save_selected_translation(shikimori_id: str | None, translation: dict) -> None:
    """Сохраняет выбранную озвучку для данного аниме и как последнюю использованную."""
    if not translation or not translation.get("id"):
        return
    record = {
        "id": str(translation["id"]),
        "name": str(translation.get("name", "")),
        "type": str(translation.get("type", "")),
    }
    with _lock:
        data = _load_locked()
        if shikimori_id:
            data["by_anime"][str(shikimori_id)] = record
        data["last_used"] = record
        _save_locked()


def get_saved_translation(shikimori_id: str | None) -> dict | None:
    """Возвращает сохранённую озвучку для указанного shikimori_id или None."""
    if not shikimori_id:
        return None
    with _lock:
        return _load_locked()["by_anime"].get(str(shikimori_id))


def get_last_used_translation() -> dict | None:
    """Возвращает последнюю выбранную пользователем озвучку вообще или None."""
    with _lock:
        return _load_locked().get("last_used")


def find_matching_translation_index(
    translations: list[dict], shikimori_id: str | None
) -> int | None:
    """Находит в списке translations индекс наиболее подходящей озвучки:
    1. Точное совпадение по id сохранённой для этого аниме озвучки.
    2. Совпадение по нормализованному названию студии/автора для этого аниме.
    3. Точное совпадение по id последней выбранной пользователем озвучки.
    4. Совпадение по нормализованному названию последней выбранной озвучки.
    Если совпадений нет, возвращает None.
    """
    if not translations:
        return None

    saved_anime = get_saved_translation(shikimori_id)
    last_used = get_last_used_translation()

    # 1-2. Проверяем сохранённую озвучку именно для этого аниме
    if saved_anime:
        saved_id = str(saved_anime.get("id"))
        for i, t in enumerate(translations):
            if str(t.get("id")) == saved_id:
                return i

        saved_norm = _normalize_name(saved_anime.get("name", ""))
        if saved_norm:
            for i, t in enumerate(translations):
                if _normalize_name(t.get("name", "")) == saved_norm:
                    return i

    # 3-4. Проверяем последнюю использованную пользователем озвучку
    if last_used:
        last_id = str(last_used.get("id"))
        for i, t in enumerate(translations):
            if str(t.get("id")) == last_id:
                return i

        last_norm = _normalize_name(last_used.get("name", ""))
        if last_norm:
            for i, t in enumerate(translations):
                if _normalize_name(t.get("name", "")) == last_norm:
                    return i

    return None


def replace_all(data: dict) -> None:
    """Полностью заменяет сохранённые озвучки (для импорта данных)."""
    global _data
    with _lock:
        _data = data if isinstance(data, dict) else {}
        _data.setdefault("by_anime", {})
        _save_locked()
