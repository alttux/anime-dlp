import time
from pathlib import Path

from anime_dlp import __version__
from anime_dlp.core.episodes import BatchResult

APP_TITLE = f"Anime Downloader v{__version__}"


def humanize_bytes(n: int) -> str:
    value = float(n)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} ГБ"


class SpeedTracker:
    def __init__(self):
        self._last_time = None
        self._last_downloaded = 0

    def update(self, downloaded: int) -> str:
        now = time.monotonic()
        if self._last_time is None:
            self._last_time = now
            self._last_downloaded = downloaded
            return ""

        elapsed = now - self._last_time
        if elapsed < 0.2:
            return ""

        delta = downloaded - self._last_downloaded
        speed = delta / elapsed if elapsed > 0 else 0
        self._last_time = now
        self._last_downloaded = downloaded
        return f"{humanize_bytes(speed)}/с"


def summarize_result(result: BatchResult, download_dir: Path) -> tuple[str, str]:
    """(заголовок, описание) итогового экрана скачивания — один текст для
    GTK и Qt."""
    if result.cancelled:
        return (
            "Скачивание отменено",
            f"Недокачанное продолжится при повторном скачивании в {download_dir}",
        )
    if result.failed:
        attempted = len(result.done) + len(result.failed)
        return (
            "Готово, но с ошибками",
            f"Скачано {len(result.done)} из {attempted}. Файлы сохранены в {download_dir}",
        )
    return "Готово!", f"Файлы сохранены в {download_dir}"
