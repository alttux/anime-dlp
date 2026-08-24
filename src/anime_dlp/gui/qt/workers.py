"""Фоновые воркеры на QThread, переносящие вызовы anime_dlp.core.* в
отдельный поток и сообщающие о результате через сигналы (аналог связки
threading.Thread + GLib.idle_add в GTK-версии)."""

from pathlib import Path

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from anime_dlp.core.anime_service import (
    get_download_link,
    get_genre_cover,
    search_anime,
)
from anime_dlp.core.cache import fetch_image_cached
from anime_dlp.core.downloader import download_episode
from anime_dlp.filenames import sanitize_filename
from anime_dlp.gui import prefetch


class SearchWorker(QThread):
    finished_search = pyqtSignal(str, list, str)

    def __init__(self, query: str, parent=None):
        super().__init__(parent)
        self.query = query

    def run(self):
        try:
            items = search_anime(self.query)
            error = ""
        except Exception as exc:
            items = []
            error = str(exc)
        self.finished_search.emit(self.query, items, error)


class AnimeInfoWorker(QThread):
    finished_info = pyqtSignal(dict, str)

    def __init__(self, shikimori_id: str, parent=None):
        super().__init__(parent)
        self.shikimori_id = shikimori_id

    def run(self):
        try:
            info = prefetch.get_or_fetch(self.shikimori_id)
            error = ""
        except Exception as exc:
            info = {}
            error = str(exc)
        self.finished_info.emit(info, error)


class PosterWorker(QThread):
    finished_poster = pyqtSignal(bytes, str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            data = fetch_image_cached(self.url, timeout=10)
            error = ""
        except requests.RequestException as exc:
            data = b""
            error = str(exc)
        self.finished_poster.emit(data, error)


class CatalogWorker(QThread):
    """Одна страница сетки обложек. loader — (cursor, limit) -> (items,
    next_cursor): популярное на «Главном» или конкретный жанр."""

    finished_page = pyqtSignal(list, str, str, int)

    def __init__(self, loader, cursor: str | None, limit: int, generation: int, parent=None):
        super().__init__(parent)
        self.loader = loader
        self.cursor = cursor
        self.limit = limit
        self.generation = generation

    def run(self):
        try:
            items, next_cursor = self.loader(self.cursor, self.limit)
            error = ""
        except Exception as exc:
            items, next_cursor, error = [], None, str(exc)
        self.finished_page.emit(items, next_cursor or "", error, self.generation)


class GenreCoversWorker(QThread):
    """Ищет обложку (топ-1 аниме) для каждого жанра по очереди и отдаёт их по
    одной. Последовательно, а не пулом: при холодном кэше это 19 запросов к
    Kodik, устраивать из них шторм незачем — карточки заполняются по ходу."""

    cover_ready = pyqtSignal(str, dict, int)

    def __init__(self, genres: list[str], generation: int, parent=None):
        super().__init__(parent)
        self.genres = genres
        self.generation = generation

    def run(self):
        for genre in self.genres:
            try:
                item = get_genre_cover(genre)
            except Exception:
                continue
            if item:
                self.cover_ready.emit(genre, item, self.generation)


class DownloadWorker(QThread):
    file_started = pyqtSignal(str, str, int, int)
    file_progress = pyqtSignal(str, int, int)
    file_done = pyqtSignal(str, str)
    file_error = pyqtSignal(str, str)
    all_done = pyqtSignal()
    fatal_error = pyqtSignal(str)

    def __init__(
        self,
        item: dict,
        translation_id: str,
        eps_to_download: list[int],
        download_dir: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.item = item
        self.translation_id = translation_id
        self.eps_to_download = eps_to_download
        self.download_dir = download_dir

    def run(self):
        try:
            sid = self.item["shikimori_id"]
            total = len(self.eps_to_download)
            started: set[str] = set()
            for index, ep in enumerate(self.eps_to_download, 1):
                safe_title = sanitize_filename(self.item["title"])
                filename = f"{safe_title}.mp4" if ep == 0 else f"{ep}.mp4"
                filepath = self.download_dir / filename
                try:
                    link, quality, _ = get_download_link(sid, ep, self.translation_id)

                    self.file_started.emit(filename, str(filepath), index, total)
                    started.add(filename)

                    def on_progress(downloaded, total_bytes, filename=filename):
                        self.file_progress.emit(filename, downloaded, total_bytes)

                    download_episode(link, filepath, quality, on_progress=on_progress)
                    self.file_done.emit(filename, str(filepath))
                except Exception as exc:
                    if filename not in started:
                        self.file_started.emit(filename, str(filepath), index, total)
                    self.file_error.emit(filename, str(exc))
            self.all_done.emit()
        except Exception as exc:
            self.fatal_error.emit(str(exc))
