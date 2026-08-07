import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from anime_dlp.config import HEADERS, NUM_THREADS


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
    progress: Progress,
    task,
    lock: threading.Lock,
):
    range_headers = {**HEADERS, "Range": f"bytes={start}-{end}"}
    response = requests.get(url, headers=range_headers, stream=True)
    response.raise_for_status()

    with open(filepath, "r+b") as f:
        f.seek(start)
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            with lock:
                progress.update(task, advance=len(chunk))


def _download_single(url: str, filepath: Path, total: int, progress: Progress, task):
    response = requests.get(url, headers=HEADERS, stream=True)
    response.raise_for_status()

    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            progress.update(task, advance=len(chunk))


def download_episode(url: str, filepath: Path, quality: int):
    full_url = f"https:{url}{quality}.mp4"

    head_response = requests.get(full_url, headers=HEADERS, stream=True)
    head_response.raise_for_status()
    total = int(head_response.headers.get("content-length", 0))
    head_response.close()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(f"Downloading {filepath.name}", total=total)

        if _supports_ranges(full_url, total):
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as f:
                f.truncate(total)

            ranges = _compute_ranges(total, NUM_THREADS)
            lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=len(ranges)) as executor:
                futures = [
                    executor.submit(
                        _download_range, full_url, filepath, start, end, progress, task, lock
                    )
                    for start, end in ranges
                ]
                for future in as_completed(futures):
                    future.result()
        else:
            _download_single(full_url, filepath, total, progress, task)
