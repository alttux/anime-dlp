from config import BASE_DIR, TOKEN_FILE


def _get_token_path():
    return BASE_DIR / TOKEN_FILE


def load_token() -> str | None:
    path = _get_token_path()
    if path.exists():
        token = path.read_text().strip()
        return token if token else None
    return None


def save_token(token: str):
    _get_token_path().write_text(token)
