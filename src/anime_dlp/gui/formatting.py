import time

from anime_dlp import __version__

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
