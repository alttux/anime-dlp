"""Скачивание одного файла: многопоточно по HTTP Range с докачкой, либо через
ffmpeg, если CDN Kodik отдаёт только HLS.

Как устроено Range-скачивание:
  * один пробный запрос `Range: bytes=0-0` сразу говорит и размер файла
    (Content-Range), и поддерживает ли сервер диапазоны (206), и конечный URL
    после редиректов — раньше на это уходило два полных GET;
  * файл режется на куски по CHUNK_SIZE, NUM_THREADS потоков разбирают их из
    общей очереди — медленное соединение задерживает только свой кусок, а не
    1/8 файла, как при статическом разбиении;
  * каждый кусок повторяется до MAX_RETRIES раз и продолжает с того байта, на
    котором оборвался;
  * данные пишутся в `<имя>.part`, готовые куски отмечаются в
    `<имя>.part.json` — после обрыва/отмены/перезапуска скачивание
    продолжается с недостающих кусков, а готовый файл появляется под своим
    именем только целиком (атомарный rename);
  * колбэк прогресса вызывается не чаще PROGRESS_INTERVAL — раньше он
    дёргался на каждые 8 КБ из восьми потоков, и GUI тонул в
    GLib.idle_add/сигналах.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from anime_dlp.config import HEADERS, NUM_THREADS
from anime_dlp.core.cache import atomic_write
from anime_dlp.core.http import TIMEOUT, get_session

ProgressCallback = Callable[[int, int], None]

CHUNK_SIZE = 8 * 1024 * 1024
READ_SIZE = 256 * 1024
MAX_RETRIES = 5
PROGRESS_INTERVAL = 0.1

_EXTINF_RE = re.compile(r"#EXTINF:([\d.]+),")
_OUT_TIME_MS_RE = re.compile(r"out_time_ms=(\d+)")
_CONTENT_RANGE_TOTAL_RE = re.compile(r"/(\d+)\s*$")


class DownloadCancelled(Exception):
    """Скачивание остановлено через cancel_event. Недокачанный `.part`
    остаётся на диске — следующий запуск продолжит с того же места."""


class _Progress:
    """Потокобезопасный счётчик байт с прореживанием вызовов колбэка."""

    def __init__(self, total: int, on_progress: ProgressCallback | None, done: int = 0):
        self.total = total
        self.done = done
        self._callback = on_progress
        self._lock = threading.Lock()
        self._last_report = 0.0

    def add(self, n: int) -> None:
        with self._lock:
            self.done += n
            now = time.monotonic()
            if now - self._last_report < PROGRESS_INTERVAL:
                return
            self._last_report = now
            done = self.done
        if self._callback:
            self._callback(done, self.total)

    def report(self) -> None:
        if self._callback:
            self._callback(self.done, self.total)


def _check_cancel(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelled


class _AnyEvent:
    """«Остановиться» — если отменил пользователь или упал соседний поток
    (тогда докачивать свои куски бессмысленно: файл всё равно не соберётся)."""

    def __init__(self, *events: threading.Event | None):
        self._events = [e for e in events if e is not None]

    def is_set(self) -> bool:
        return any(e.is_set() for e in self._events)


def _part_paths(filepath: Path) -> tuple[Path, Path]:
    return (
        filepath.with_name(filepath.name + ".part"),
        filepath.with_name(filepath.name + ".part.json"),
    )


def _probe(url: str) -> tuple[requests.Response | None, int, bool, str]:
    """Возвращает (response, total, supports_ranges, final_url).

    response — открытый поток тела ответа, только если сервер проигнорировал
    Range и отдал файл целиком (200): его сразу и дочитываем, без повторного
    запроса. При 206 или ошибке response уже закрыт (None)."""
    response = get_session().get(
        url, headers={"Range": "bytes=0-0"}, stream=True, timeout=TIMEOUT
    )
    if response.status_code == 206:
        match = _CONTENT_RANGE_TOTAL_RE.search(response.headers.get("Content-Range", ""))
        final_url = response.url
        response.close()
        if match and int(match.group(1)) > 0:
            return None, int(match.group(1)), True, final_url
        # Диапазоны есть, но размер неизвестен — качаем одним потоком.
        response = get_session().get(url, stream=True, timeout=TIMEOUT)
        response.raise_for_status()
        return response, int(response.headers.get("content-length", 0)), False, final_url
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    return response, total, False, response.url


def _load_done_chunks(state_path: Path, part_path: Path, total: int, chunk_size: int) -> set[int]:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if (
        not part_path.exists()
        or state.get("total") != total
        or state.get("chunk_size") != chunk_size
    ):
        return set()
    return {i for i in state.get("done", []) if isinstance(i, int)}


def _download_chunk(
    urls: list[str],
    part_path: Path,
    start: int,
    end: int,
    progress: _Progress,
    stop: _AnyEvent,
) -> None:
    """Качает байты [start, end] с повторами. После обрыва повтор продолжает
    с первого недописанного байта, уже засчитанные в прогресс байты не
    скачиваются и не считаются второй раз."""
    position = start
    for attempt in range(MAX_RETRIES):
        _check_cancel(stop)
        # Первая попытка — по URL после редиректов (экономит лишний запрос на
        # каждый кусок); повторы — по исходному, вдруг конечная ссылка CDN
        # протухла.
        url = urls[0] if attempt == 0 else urls[-1]
        try:
            response = get_session().get(
                url,
                headers={"Range": f"bytes={position}-{end}"},
                stream=True,
                timeout=TIMEOUT,
            )
            with response:
                if response.status_code != 206:
                    raise requests.HTTPError(
                        f"сервер вернул {response.status_code} вместо 206", response=response
                    )
                with open(part_path, "r+b") as f:
                    f.seek(position)
                    for data in response.iter_content(chunk_size=READ_SIZE):
                        _check_cancel(stop)
                        remaining = end + 1 - position
                        if len(data) > remaining:
                            data = data[:remaining]
                        f.write(data)
                        position += len(data)
                        progress.add(len(data))
                        if position > end:
                            return
            if position > end:
                return
            raise requests.ConnectionError("соединение закрыто до конца диапазона")
        except (requests.RequestException, OSError):
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(min(2**attempt, 10))


def _download_ranges(
    urls: list[str],
    filepath: Path,
    total: int,
    on_progress: ProgressCallback | None,
    cancel_event: threading.Event | None,
) -> None:
    part_path, state_path = _part_paths(filepath)
    chunk_size = max(CHUNK_SIZE, -(-total // 10_000))  # не больше ~10к кусков
    chunks = [
        (index, start, min(start + chunk_size, total) - 1)
        for index, start in enumerate(range(0, total, chunk_size))
    ]

    done = _load_done_chunks(state_path, part_path, total, chunk_size)
    if not done:
        with open(part_path, "wb") as f:
            f.truncate(total)
    already = sum(end - start + 1 for index, start, end in chunks if index in done)
    progress = _Progress(total, on_progress, done=already)
    progress.report()

    state_lock = threading.Lock()

    def save_state():
        payload = {"total": total, "chunk_size": chunk_size, "done": sorted(done)}
        atomic_write(state_path, json.dumps(payload).encode("utf-8"))

    pending = deque(c for c in chunks if c[0] not in done)
    queue_lock = threading.Lock()
    failed = threading.Event()
    stop = _AnyEvent(cancel_event, failed)

    def worker():
        while not stop.is_set():
            with queue_lock:
                if not pending:
                    return
                index, start, end = pending.popleft()
            try:
                _download_chunk(urls, part_path, start, end, progress, stop)
            except BaseException:
                failed.set()
                raise
            with state_lock:
                done.add(index)
                save_state()

    workers = max(1, min(NUM_THREADS, len(pending)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="download") as executor:
        futures = [executor.submit(worker) for _ in range(workers)]
    _check_cancel(cancel_event)
    errors = [f.exception() for f in futures if f.exception() is not None]
    # DownloadCancelled у остальных потоков — следствие failed, а не причина.
    real = [e for e in errors if not isinstance(e, DownloadCancelled)]
    if real:
        raise real[0]

    os.replace(part_path, filepath)
    state_path.unlink(missing_ok=True)
    progress.report()


def _download_single(
    response: requests.Response,
    filepath: Path,
    total: int,
    on_progress: ProgressCallback | None,
    cancel_event: threading.Event | None,
) -> None:
    part_path, _ = _part_paths(filepath)
    progress = _Progress(total, on_progress)
    progress.report()
    with response, open(part_path, "wb") as f:
        for data in response.iter_content(chunk_size=READ_SIZE):
            _check_cancel(cancel_event)
            f.write(data)
            progress.add(len(data))
    if total and progress.done < total:
        raise requests.ConnectionError("соединение закрыто до конца файла")
    os.replace(part_path, filepath)
    if not progress.total:
        progress.total = progress.done
    progress.report()


def _playlist_duration_ms(playlist_text: str) -> int:
    return int(sum(float(m) for m in _EXTINF_RE.findall(playlist_text)) * 1000)


def _download_via_hls(
    m3u8_url: str,
    filepath: Path,
    on_progress: ProgressCallback | None,
    cancel_event: threading.Event | None,
):
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "Для скачивания этой серии требуется ffmpeg (видео доступно только "
            "в формате HLS). Установите ffmpeg и повторите попытку."
        )

    playlist_response = get_session().get(m3u8_url, timeout=TIMEOUT)
    playlist_response.raise_for_status()
    total_ms = _playlist_duration_ms(playlist_response.text)

    if on_progress:
        on_progress(0, total_ms)

    part_path, _ = _part_paths(filepath)
    header_lines = f"Referer: {HEADERS['Referer']}\r\nUser-Agent: {HEADERS['User-Agent']}\r\n"
    cmd = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-headers",
        header_lines,
        "-i",
        m3u8_url,
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        # У .part нет расширения контейнера — формат задаём явно.
        "-f",
        "mp4",
        "-progress",
        "pipe:1",
        "-nostats",
        "-loglevel",
        "error",
        str(part_path),
    ]
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    # stderr читаем параллельно: если ffmpeg напишет туда больше размера
    # буфера пайпа, пока мы читаем только stdout, оба процесса встанут.
    stderr_chunks: list[str] = []
    stderr_thread = threading.Thread(
        target=lambda: stderr_chunks.append(process.stderr.read()), daemon=True
    )
    stderr_thread.start()

    # Отдельный сторож нужен, потому что чтение stdout блокирующее: пока
    # ffmpeg ждёт сеть, строки прогресса не приходят и проверить флаг
    # в цикле негде.
    def watch_cancel():
        if cancel_event is not None:
            while process.poll() is None:
                if cancel_event.wait(0.5):
                    process.terminate()
                    return

    threading.Thread(target=watch_cancel, daemon=True).start()

    last_report = 0.0
    for line in process.stdout:
        match = _OUT_TIME_MS_RE.match(line)
        now = time.monotonic()
        if match and on_progress and now - last_report >= PROGRESS_INTERVAL:
            last_report = now
            on_progress(min(int(match.group(1)) // 1000, total_ms), total_ms)

    process.wait()
    stderr_thread.join()
    if process.returncode != 0:
        # HLS докачивать не умеем — обрывок без пользы, убираем.
        part_path.unlink(missing_ok=True)
        _check_cancel(cancel_event)
        raise RuntimeError(
            f"Ошибка ffmpeg при скачивании HLS-потока: {''.join(stderr_chunks).strip()}"
        )

    os.replace(part_path, filepath)
    if on_progress and total_ms:
        on_progress(total_ms, total_ms)


def download_episode(
    url: str,
    filepath: Path,
    quality: int,
    on_progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
):
    """Скачивает серию в filepath. Бросает DownloadCancelled, если
    cancel_event выставили во время скачивания."""
    _check_cancel(cancel_event)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    full_url = f"https:{url}{quality}.mp4"

    try:
        response, total, supports_ranges, final_url = _probe(full_url)
    except requests.HTTPError as exc:
        if exc.response is None:
            raise
        exc.response.close()
        hls_url = f"https:{url}{quality}.mp4:hls:manifest.m3u8"
        _download_via_hls(hls_url, filepath, on_progress, cancel_event)
        return

    if supports_ranges and total > 0:
        # Файл уже скачан целиком (например, повторный запуск «всего сезона»).
        if filepath.exists() and filepath.stat().st_size == total:
            if on_progress:
                on_progress(total, total)
            return
        _download_ranges([final_url, full_url], filepath, total, on_progress, cancel_event)
    else:
        _download_single(response, filepath, total, on_progress, cancel_event)
