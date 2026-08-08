import re
import shutil
import subprocess
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from anime_dlp.config import HEADERS, NUM_THREADS

ProgressCallback = Callable[[int, int], None]

_EXTINF_RE = re.compile(r"#EXTINF:([\d.]+),")
_OUT_TIME_MS_RE = re.compile(r"out_time_ms=(\d+)")


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


def _playlist_duration_ms(playlist_text: str) -> int:
    return int(sum(float(m) for m in _EXTINF_RE.findall(playlist_text)) * 1000)


def _download_via_hls(
    m3u8_url: str, filepath: Path, on_progress: ProgressCallback | None
):
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "Для скачивания этой серии требуется ffmpeg (видео доступно только "
            "в формате HLS). Установите ffmpeg и повторите попытку."
        )

    playlist_response = requests.get(m3u8_url, headers=HEADERS)
    playlist_response.raise_for_status()
    total_ms = _playlist_duration_ms(playlist_response.text)

    if on_progress:
        on_progress(0, total_ms)

    filepath.parent.mkdir(parents=True, exist_ok=True)

    header_lines = f"Referer: {HEADERS['Referer']}\r\nUser-Agent: {HEADERS['User-Agent']}\r\n"
    cmd = [
        "ffmpeg",
        "-y",
        "-headers",
        header_lines,
        "-i",
        m3u8_url,
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        "-progress",
        "pipe:1",
        "-loglevel",
        "error",
        str(filepath),
    ]
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    for line in process.stdout:
        match = _OUT_TIME_MS_RE.match(line)
        if match and on_progress:
            on_progress(min(int(match.group(1)) // 1000, total_ms), total_ms)

    stderr = process.stderr.read()
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"Ошибка ffmpeg при скачивании HLS-потока: {stderr}")

    if on_progress and total_ms:
        on_progress(total_ms, total_ms)


def download_episode(
    url: str,
    filepath: Path,
    quality: int,
    on_progress: ProgressCallback | None = None,
):
    full_url = f"https:{url}{quality}.mp4"

    head_response = requests.get(full_url, headers=HEADERS, stream=True)
    if head_response.status_code >= 400:
        head_response.close()
        hls_url = f"https:{url}{quality}.mp4:hls:manifest.m3u8"
        _download_via_hls(hls_url, filepath, on_progress)
        return

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
