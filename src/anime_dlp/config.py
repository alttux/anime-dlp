from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOKEN_FILE = ".kodik_token"
DOWNLOAD_DIR = BASE_DIR / "downloads"
NUM_THREADS = 8
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://kodik.info/",
}
