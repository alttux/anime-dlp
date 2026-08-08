from anime_dlp.config import DATA_DIR, TOKEN_FILE


def _get_token_path():
    return DATA_DIR / TOKEN_FILE


def load_token() -> str | None:
    path = _get_token_path()
    if path.exists():
        token = path.read_text().strip()
        return token if token else None
    return None


def save_token(token: str):
    path = _get_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token)
