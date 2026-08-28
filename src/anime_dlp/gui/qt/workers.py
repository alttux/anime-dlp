"""Фоновые воркеры на QThread, переносящие вызовы anime_dlp.core.* в
отдельный поток и сообщающие о результате через сигналы (аналог связки
threading.Thread + GLib.idle_add в GTK-версии)."""

from pathlib import Path

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from anime_dlp.core.anime_service import get_download_link, search_anime
from anime_dlp.core.cache import fetch_image_cached
from anime_dlp.core.downloader import download_episode
from anime_dlp.filenames import sanitize_filename
from anime_dlp.gui import prefetch

# Живые воркеры, ещё не завершившие run(). Смысл — держать ссылку на
# Python-обёртку QThread на всё время работы потока: у воркеров больше нет
# родителя-виджета (см. ниже), поэтому обёртку никто, кроме этого множества,
# не удерживает. Если её соберёт GC, пока поток работает, PyQt вызовет
# C++-delete у ещё живого QThread → Qt делает qFatal()/abort() ("QThread:
# Destroyed while thread is still running"). Раньше эту роль играл parent=<виджет>,
# но виджет уничтожается при навигации/reload раньше, чем поток дочитает сеть.
#
# Меняется только из главного потока: конструирование воркеров происходит в
# __init__ виджетов, _cleanup приходит очередью в главный цикл, stop_all_workers
# вызывается из aboutToQuit. Поэтому блокировка не нужна.
_active_workers: set["_BaseWorker"] = set()


class _BaseWorker(QThread):
    """База для всех фоновых воркеров: без родителя, сам себя регистрирует на
    время работы и сам себя удаляет после завершения (fire-and-forget)."""

    def __init__(self):
        super().__init__()
        self.setObjectName(type(self).__name__)
        _active_workers.add(self)
        self.finished.connect(self._cleanup)

    def _cleanup(self):
        # finished доставляется очередью в главный поток уже после возврата из
        # run(), поэтому deleteLater() здесь безопасен; wait() звать нельзя.
        _active_workers.discard(self)
        self.deleteLater()


def stop_all_workers(wait_ms: int = 3000) -> None:
    """Останавливает все ещё работающие воркеры при выходе из приложения.
    Сначала вежливо (requestInterruption + ожидание), затем принудительно."""
    for worker in list(_active_workers):
        try:
            worker.requestInterruption()
            if not worker.wait(wait_ms):
                worker.terminate()
                worker.wait()
        except RuntimeError:
            # Обёртка C++-объекта уже удалена — воркер и так завершён.
            pass
    _active_workers.clear()


class SearchWorker(_BaseWorker):
    finished_search = pyqtSignal(str, list, str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            items = search_anime(self.query)
            error = ""
        except Exception as exc:
            items = []
            error = str(exc)
        self.finished_search.emit(self.query, items, error)


class AnimeInfoWorker(_BaseWorker):
    finished_info = pyqtSignal(dict, str)

    def __init__(self, shikimori_id: str):
        super().__init__()
        self.shikimori_id = shikimori_id

    def run(self):
        try:
            info = prefetch.get_or_fetch(self.shikimori_id)
            error = ""
        except Exception as exc:
            info = {}
            error = str(exc)
        self.finished_info.emit(info, error)


class PosterWorker(_BaseWorker):
    finished_poster = pyqtSignal(bytes, str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            data = fetch_image_cached(self.url, timeout=10)
            error = ""
        except requests.RequestException as exc:
            data = b""
            error = str(exc)
        self.finished_poster.emit(data, error)


class CatalogWorker(_BaseWorker):
    """Одна страница сетки обложек. loader — (cursor, limit) -> (items,
    next_cursor): популярное на «Главном» или конкретный жанр."""

    finished_page = pyqtSignal(list, str, str, int)

    def __init__(self, loader, cursor: str | None, limit: int, generation: int):
        super().__init__()
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


class DownloadWorker(_BaseWorker):
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
    ):
        super().__init__()
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
                if self.isInterruptionRequested():
                    break
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
