# Имена, зарезервированные Windows (независимо от регистра и расширения) —
# на Linux/macOS они бы прошли без проблем, но файл с таким именем нельзя
# будет создать на Windows.
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_filename(name: str) -> str:
    allowed = set(" .-_()[]")
    cleaned = "".join(c for c in name if c.isalnum() or c in allowed).strip()
    # Windows не разрешает имена файлов, заканчивающиеся точкой или пробелом.
    cleaned = cleaned.rstrip(" .")
    if not cleaned:
        return "anime"
    if cleaned.upper() in _WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned
