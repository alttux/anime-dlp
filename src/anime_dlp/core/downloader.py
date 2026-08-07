import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from anime_dlp.config import HEADERS, NUM_THREADS

ProgressCallback = Callable[[int, int], None]


def _supports_ranges(url: str, total: int) -> bool:
    if total <= 0:
        return False
    probe_headers = {**HEADERS, "Range": "bytes=0-0"}
    response = requests.get(url, headers=probe_headers, stream=True)
    response.close()
    return response.status_code == 206


def _compute_ranges(total: int, num_threads: int) -> list[tuple[int, int]]:
    num_threads = max(1, min(num_threads, total))
    chunk_size = total // num_threads
    ranges = []
    for i in range(num_threads):
        start = i * chunk_size
        end = start + chunk_size - 1 if i < num_threads - 1 else total - 1
        ranges.append((start, end))
    return ranges


def _download_range(
    url: str,
    filepath: Path,
    start: int,
    end: int,
    total: int,
    downloaded: list[int],
    lock: threading.Lock,
    on_progress: ProgressCallback | None,
):
    range_headers = {**HEADERS, "Range": f"bytes={start}-{end}"}
    response = requests.get(url, headers=range_headers, stream=True)
    response.raise_for_status()

    with open(filepath, "r+b") as f:
        f.seek(start)
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            with lock:
                downloaded[0] += len(chunk)
                if on_progress:
                    on_progress(downloaded[0], total)


def _download_single(
    url: str, filepath: Path, total: int, on_progress: ProgressCallback | None
):
    response = requests.get(url, headers=HEADERS, stream=True)
    response.raise_for_status()

    downloaded = 0
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if on_progress:
                on_progress(downloaded, total)


def download_episode(
    url: str,
    filepath: Path,
    quality: int,
    on_progress: ProgressCallback | None = None,
):
    full_url = f"https:{url}{quality}.mp4"

    head_response = requests.get(full_url, headers=HEADERS, stream=True)
    head_response.raise_for_status()
    total = int(head_response.headers.get("content-length", 0))
    head_response.close()

    if on_progress:
        on_progress(0, total)

    if _supports_ranges(full_url, total):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            f.truncate(total)

        ranges = _compute_ranges(total, NUM_THREADS)
        lock = threading.Lock()
        downloaded = [0]

        with ThreadPoolExecutor(max_workers=len(ranges)) as executor:
            futures = [
                executor.submit(
                    _download_range,
                    full_url,
                    filepath,
                    start,
                    end,
                    total,
                    downloaded,
                    lock,
                    on_progress,
                )
                for start, end in ranges
            ]
            for future in as_completed(futures):
                future.result()
    else:
        _download_single(full_url, filepath, total, on_progress)
