import re
from dataclasses import dataclass
from datetime import datetime

from anime_dlp.labels import KIND_MAP, STATUS_MAP

_SEASON_BY_MONTH = {
    12: "Зима", 1: "Зима", 2: "Зима",
    3: "Весна", 4: "Весна", 5: "Весна",
    6: "Лето", 7: "Лето", 8: "Лето",
    9: "Осень", 10: "Осень", 11: "Осень",
}

_AIRED_AT_MONTH_RE = re.compile(r"^\d{4}-(\d{2})")


@dataclass
class AnimeInfo:
    description: str | None
    genres: list[str]
    studios: list[str]
    status: str | None
    score: float | None
    votes: int | None
    episodes_total: int | None
    episodes_aired: int | None
    poster_url: str | None
    kind: str | None
    year: int | None
    season: str | None
    age_rating: str | None
    title_orig: str | None
    duration: int | None


def _first_text(material: dict, *keys: str) -> str | None:
    for key in keys:
        value = material.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_list(material: dict, *keys: str) -> list[str]:
    for key in keys:
        value = material.get(key)
        if isinstance(value, list) and value:
            return [str(v) for v in value if v]
    return []


def _to_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result or None


def _to_int(value) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result or None


def _derive_season(aired_at) -> str | None:
    """Kodik/Shikimori не хранят время года отдельным полем — выводим его
    из месяца премьеры (material_data["aired_at"]). Не бросает исключений,
    просто возвращает None, если дату не удалось разобрать."""
    if not isinstance(aired_at, str) or not aired_at.strip():
        return None
    try:
        month = datetime.fromisoformat(aired_at[:10]).month
    except ValueError:
        match = _AIRED_AT_MONTH_RE.match(aired_at)
        if not match:
            return None
        month = int(match.group(1))
    return _SEASON_BY_MONTH.get(month)


def _derive_age_rating(material: dict) -> str | None:
    rating_mpaa = material.get("rating_mpaa")
    if isinstance(rating_mpaa, str) and rating_mpaa.strip():
        return rating_mpaa.strip()
    minimal_age = _to_int(material.get("minimal_age"))
    if minimal_age:
        return f"{minimal_age}+"
    return None


def extract_anime_info(item: dict) -> AnimeInfo:
    material = item.get("material_data") or {}

    description = _first_text(material, "anime_description", "description")
    genres = _first_list(material, "anime_genres", "genres", "all_genres")
    studios = _first_list(material, "anime_studios")

    raw_status = material.get("anime_status")
    status = STATUS_MAP.get(raw_status, raw_status) if raw_status else None

    score = _to_float(material.get("shikimori_rating"))
    votes = _to_int(material.get("shikimori_votes")) if score is not None else None

    episodes_total = _to_int(material.get("episodes_total"))
    episodes_aired = _to_int(material.get("episodes_aired"))

    poster_url = _first_text(material, "anime_poster_url", "poster_url")

    raw_kind = material.get("anime_kind")
    if raw_kind:
        kind = KIND_MAP.get(raw_kind, raw_kind.capitalize())
    else:
        kind = None

    year = _to_int(material.get("year")) or _to_int(item.get("year"))
    season = _derive_season(material.get("aired_at"))
    age_rating = _derive_age_rating(material)

    title_orig = item.get("title_orig")
    title_orig = title_orig.strip() if isinstance(title_orig, str) else None
    if title_orig and title_orig == item.get("title"):
        title_orig = None

    duration = _to_int(material.get("duration"))

    return AnimeInfo(
        description=description,
        genres=genres,
        studios=studios,
        status=status,
        score=score,
        votes=votes,
        episodes_total=episodes_total,
        episodes_aired=episodes_aired,
        poster_url=poster_url,
        kind=kind,
        year=year,
        season=season,
        age_rating=age_rating,
        title_orig=title_orig,
        duration=duration,
    )


def has_any_info(info: AnimeInfo) -> bool:
    return bool(
        info.description
        or info.genres
        or info.studios
        or info.status
        or info.score
        or info.episodes_total
        or info.episodes_aired
    )


def build_detail_rows(info: AnimeInfo) -> list[tuple[str, str]]:
    """Упорядоченные пары (подпись, значение) для компактного блока
    характеристик в шапке страницы аниме. Строки с отсутствующими данными
    просто не включаются в список — GUI не должен показывать пустые
    значения."""
    rows: list[tuple[str, str]] = []

    if info.kind:
        rows.append(("Тип", info.kind))
    if info.year:
        rows.append(("Год", str(info.year)))
    if info.season:
        rows.append(("Сезон", info.season))
    if info.age_rating:
        rows.append(("Возрастной рейтинг", info.age_rating))

    if info.episodes_total or info.episodes_aired:
        if info.episodes_total and info.episodes_aired and info.episodes_aired != info.episodes_total:
            episodes = f"{info.episodes_aired}/{info.episodes_total}"
        else:
            episodes = str(info.episodes_total or info.episodes_aired)
        rows.append(("Эпизоды", episodes))

    if info.status:
        rows.append(("Статус", info.status))

    if info.score:
        rating = str(info.score)
        if info.votes:
            rating += f" ({info.votes} голосов)"
        rows.append(("Рейтинг", rating))

    if info.studios:
        rows.append(("Студия", ", ".join(info.studios)))

    return rows
