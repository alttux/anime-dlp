import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOKEN_FILE = ".kodik_token"

# Внутри Flatpak каталог программы (/app) смонтирован только для чтения,
# поэтому и загрузки, и токен уходят в пользовательские каталоги.
IS_FLATPAK = Path("/.flatpak-info").exists()

# Собранный PyInstaller-исполняемый файл распаковывает модули во временный
# каталог (sys._MEIPASS), который удаляется после завершения программы —
# писать туда токен/загрузки нельзя, нужны постоянные пользовательские папки.
IS_FROZEN = getattr(sys, "frozen", False)


def _user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "anime-dlp"


def _user_cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "anime-dlp"


if IS_FLATPAK:
    DATA_DIR = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    DOWNLOAD_DIR = Path.home() / "Downloads"
elif IS_FROZEN:
    DATA_DIR = _user_data_dir()
    DOWNLOAD_DIR = Path.home() / "Downloads"
else:
    DATA_DIR = BASE_DIR
    DOWNLOAD_DIR = BASE_DIR / "downloads"

# Кэш (обложки, метаданные) всегда хранится в настоящей пользовательской
# cache-директории, даже при запуске из исходников — в отличие от DATA_DIR,
# кэшу незачем засорять дерево исходников.
if IS_FLATPAK:
    CACHE_DIR = (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "anime-dlp"
    )
else:
    CACHE_DIR = _user_cache_dir()

NUM_THREADS = 8
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://kodik.info/",
}
