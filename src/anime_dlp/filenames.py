def sanitize_filename(name: str) -> str:
    allowed = set(" .-_()[]")
    cleaned = "".join(c for c in name if c.isalnum() or c in allowed).strip()
    return cleaned or "anime"
