"""Хранилище настроек приложения и резервное копирование данных.

Хранит настройки интерфейса (тема, цветовая палитра, директория скачивания,
запрос пути перед скачиванием) в DATA_DIR/settings.json, а также предоставляет
функции полного экспорта и импорта всех пользовательских данных (настройки,
история просмотров, озвучки, избранное со статусами).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import threading

from anime_dlp import about
from anime_dlp.config import DATA_DIR, DOWNLOAD_DIR, SETTINGS_FILE
from anime_dlp.core.cache import atomic_write

_lock = threading.Lock()
_settings_data: dict | None = None

DEFAULT_SETTINGS = {
    "theme": "system",  # "system", "light", "dark"
    "palette": "system",  # "system", "gruvbox", "catppuccin", "monokai", "tokyo_night", "lgbtq"
    "download_dir": str(DOWNLOAD_DIR),
    "ask_download_folder": True,
}


def _path() -> Path:
    return DATA_DIR / SETTINGS_FILE


def _load_locked() -> dict:
    global _settings_data
    if _settings_data is None:
        try:
            raw = json.loads(_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        _settings_data = dict(DEFAULT_SETTINGS)
        if isinstance(raw, dict):
            _settings_data.update(raw)
    return _settings_data


def _save_locked() -> None:
    atomic_write(_path(), json.dumps(_settings_data, ensure_ascii=False, indent=2).encode("utf-8"))


def load_settings() -> dict:
    with _lock:
        return dict(_load_locked())


def save_settings(settings: dict) -> None:
    with _lock:
        data = _load_locked()
        data.update(settings)
        _save_locked()


def get_setting(key: str, default=None):
    with _lock:
        return _load_locked().get(key, default if default is not None else DEFAULT_SETTINGS.get(key))


def set_setting(key: str, value) -> None:
    with _lock:
        data = _load_locked()
        data[key] = value
        _save_locked()


def export_all_data() -> dict:
    """Формирует единый словарь со всеми данными приложения для экспорта:
    - настройки (тема, палитра, путь загрузки, флаг запроса папки);
    - избранное с разделением на просмотренность (Просмотрено / Начато / Не начато);
    - история просмотров и сохранённые позиции;
    - сохранённые варианты озвучки;
    - токен Kodik.
    """
    from anime_dlp.core import favorites, token_manager, translations, watch_history

    items = favorites.load()
    favorites_by_status: dict[str, list[dict]] = {
        watch_history.STATUS_WATCHED: [],
        watch_history.STATUS_IN_PROGRESS: [],
        watch_history.STATUS_NOT_STARTED: [],
    }
    for item in items:
        status = watch_history.get_watch_status(item)
        favorites_by_status.setdefault(status, []).append(item)

    return {
        "version": 1,
        "app_version": about.VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "settings": load_settings(),
        "favorites": items,
        "favorites_by_status": favorites_by_status,
        "watched": watch_history._load_locked(),
        "translations": translations._load_locked(),
        "token": token_manager.load_token(),
    }


def export_all_data_to_file(path: Path) -> None:
    data = export_all_data()
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    atomic_write(path, payload)


def import_all_data(data: dict) -> bool:
    """Импортирует все данные из словаря резервной копии. Возвращает True при успехе."""
    if not isinstance(data, dict):
        return False

    from anime_dlp.core import favorites, token_manager, translations, watch_history

    # 1. Настройки
    imported_settings = data.get("settings")
    if isinstance(imported_settings, dict):
        save_settings(imported_settings)

    # 2. Избранное
    imported_favorites = data.get("favorites")
    if isinstance(imported_favorites, list):
        favorites.replace_all(imported_favorites)
    elif isinstance(data.get("favorites_by_status"), dict):
        merged = []
        for group in data["favorites_by_status"].values():
            if isinstance(group, list):
                merged.extend(group)
        favorites.replace_all(merged)

    # 3. История просмотров
    imported_watched = data.get("watched")
    if isinstance(imported_watched, dict):
        watch_history.replace_all(imported_watched)

    # 4. Озвучки
    imported_translations = data.get("translations")
    if isinstance(imported_translations, dict):
        translations.replace_all(imported_translations)

    # 5. Токен
    imported_token = data.get("token")
    if isinstance(imported_token, str) and imported_token.strip():
        token_manager.save_token(imported_token.strip())

    return True


def import_all_data_from_file(path: Path) -> bool:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return False
    return import_all_data(data)
