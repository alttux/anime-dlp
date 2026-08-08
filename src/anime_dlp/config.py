import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOKEN_FILE = ".kodik_token"

# Внутри Flatpak каталог программы (/app) смонтирован только для чтения,
# поэтому и загрузки, и токен уходят в пользовательские каталоги.
IS_FLATPAK = Path("/.flatpak-info").exists()

if IS_FLATPAK:
    DATA_DIR = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    DOWNLOAD_DIR = Path.home() / "Downloads"
else:
    DATA_DIR = BASE_DIR
    DOWNLOAD_DIR = BASE_DIR / "downloads"

NUM_THREADS = 8
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://kodik.info/",
}
