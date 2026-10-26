"""Скачивание набора серий — общий сценарий для CLI и обоих GUI-бэкендов.

Раньше цикл «получить ссылку → скачать → сообщить» был скопирован трижды
(cli/app.py, gtk/download_page.py, qt/workers.py) и между сериями простаивал:
get_link — это несколько запросов к Kodik, которые выполнялись только после
того, как предыдущая серия докачалась. Здесь ссылка на следующую серию
запрашивается в фоне, пока качается текущая.
"""

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import requests

from anime_dlp.core.anime_service import get_download_link
from anime_dlp.core.downloader import DownloadCancelled, download_episode
from anime_dlp.filenames import sanitize_filename


@dataclass(frozen=True)
class EpisodeJob:
    episode: int  # 0 — фильм
    filename: str
    filepath: Path
    index: int  # 1-based номер в очереди
    total: int  # длина очереди


class DownloadEvents:
    """Колбэки хода скачивания. Вызываются из фонового потока — GUI обязан
    сам перекинуть их в главный цикл (GLib.idle_add / сигналы Qt)."""

    def on_start(self, job: EpisodeJob, quality: int) -> None: ...
    def on_progress(self, job: EpisodeJob, downloaded: int, total: int) -> None: ...
    def on_done(self, job: EpisodeJob) -> None: ...
    def on_error(self, job: EpisodeJob, message: str) -> None: ...


@dataclass
class BatchResult:
    done: list[EpisodeJob]
    failed: list[EpisodeJob]
    cancelled: bool


def episode_filename(title: str, episode: int) -> str:
    return f"{sanitize_filename(title)}.mp4" if episode == 0 else f"{episode}.mp4"


def plan_jobs(item: dict, episodes: list[int], download_dir: Path) -> list[EpisodeJob]:
    total = len(episodes)
    jobs = []
    for index, episode in enumerate(episodes, 1):
        filename = episode_filename(item["title"], episode)
        jobs.append(EpisodeJob(episode, filename, download_dir / filename, index, total))
    return jobs


# Все запущенные пакеты — чтобы при выходе из GUI остановить скачивание (и
# ffmpeg) у всех сразу, а не оставлять фоновые потоки/процессы.
_active: set[threading.Event] = set()
_active_lock = threading.Lock()


def cancel_all() -> None:
    with _active_lock:
        for event in _active:
            event.set()


def download_episodes(
    item: dict,
    translation_id: str,
    episodes: list[int],
    download_dir: Path,
    events: DownloadEvents,
    cancel_event: threading.Event | None = None,
    on_job_start: Callable[[EpisodeJob], None] | None = None,
) -> BatchResult:
    """Последовательно качает серии, ссылку на следующую запрашивая заранее.

    Ошибка одной серии не останавливает остальные (как и раньше); отмена
    останавливает всё и оставляет `.part`-файл для докачки.
    on_job_start вызывается перед запросом ссылки — CLI показывает спиннер."""
    cancel_event = cancel_event or threading.Event()
    with _active_lock:
        _active.add(cancel_event)

    sid = item["shikimori_id"]
    jobs = plan_jobs(item, episodes, download_dir)
    result = BatchResult(done=[], failed=[], cancelled=False)

    def fetch_link(episode: int):
        return get_download_link(sid, episode, translation_id)

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="link-prefetch")
    next_link: Future | None = executor.submit(fetch_link, jobs[0].episode) if jobs else None
    try:
        for position, job in enumerate(jobs):
            if cancel_event.is_set():
                result.cancelled = True
                break
            if on_job_start:
                on_job_start(job)
            link_future = next_link
            next_link = (
                executor.submit(fetch_link, jobs[position + 1].episode)
                if position + 1 < len(jobs)
                else None
            )
            started = False
            try:
                link, quality, _ = link_future.result()
                events.on_start(job, quality)
                started = True

                def on_progress(downloaded: int, total: int, job=job):
                    events.on_progress(job, downloaded, total)

                try:
                    download_episode(link, job.filepath, quality, on_progress, cancel_event)
                except requests.RequestException:
                    # Ссылка могла протухнуть, пока ждала своей очереди (её
                    # получили заранее) — одна попытка со свежей ссылкой.
                    link, quality, _ = fetch_link(job.episode)
                    download_episode(link, job.filepath, quality, on_progress, cancel_event)
                result.done.append(job)
                events.on_done(job)
            except DownloadCancelled:
                result.cancelled = True
                break
            except Exception as exc:
                if not started:
                    events.on_start(job, 0)
                result.failed.append(job)
                events.on_error(job, str(exc) or type(exc).__name__)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
        with _active_lock:
            _active.discard(cancel_event)
    return result
