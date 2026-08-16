"""Дисковый кэш для часто используемых сетевых данных (обложки, метаданные).

Два независимых хранилища под config.CACHE_DIR:
  images/<sha256(url)>.img   — сырые байты изображения
  meta/<sha256(key)>.json    — {"fetched_at": <unix ts>, "data": <json>}

Ключи хэшируются, чтобы избежать проблем с длиной/спецсимволами (кириллица
в поисковых запросах) в именах файлов. Запись атомарна (tmp + os.replace),
чтобы не оставлять битые файлы при принудительном завершении программы.
"""

import hashlib
import json
import os
import time
from pathlib import Path

import requests

from anime_dlp.config import CACHE_DIR

IMAGE_TTL_SECONDS = 7 * 24 * 3600
META_TTL_SECONDS = 24 * 3600

_IMAGES_DIR = CACHE_DIR / "images"
_META_DIR = CACHE_DIR / "meta"


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _image_path(url: str) -> Path:
    return _IMAGES_DIR / f"{_hash(url)}.img"


def _meta_path(key: str) -> Path:
    return _META_DIR / f"{_hash(key)}.json"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(data)
    os.replace(tmp_path, path)


def get_cached_image(url: str, max_age: float = IMAGE_TTL_SECONDS) -> bytes | None:
    path = _image_path(url)
    try:
        if time.time() - path.stat().st_mtime > max_age:
            return None
        return path.read_bytes()
    except OSError:
        return None


def store_image(url: str, data: bytes) -> None:
    _atomic_write(_image_path(url), data)


def get_cached_json(key: str, max_age: float = META_TTL_SECONDS):
    path = _meta_path(key)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if time.time() - payload.get("fetched_at", 0) > max_age:
        return None
    return payload.get("data")


def store_json(key: str, data) -> None:
    payload = json.dumps({"fetched_at": time.time(), "data": data}, ensure_ascii=False)
    _atomic_write(_meta_path(key), payload.encode("utf-8"))


def fetch_image_cached(url: str, timeout: float = 10) -> bytes:
    """Кэш-затем-сеть с write-through: возвращает кэшированные байты, если
    они есть и не устарели, иначе скачивает, сохраняет в кэш и возвращает."""
    cached = get_cached_image(url)
    if cached is not None:
        return cached
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    data = response.content
    store_image(url, data)
    return data
